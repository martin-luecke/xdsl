from xdsl.dialects.scf import Scf, If

from xdsl.printer import Printer
from xdsl.dialects.builtin import Builtin, IntegerAttr, i32, i64
from xdsl.parser import Parser
from xdsl.dialects.std import Std
from xdsl.dialects.arith import Arith, Constant, Addi, Muli
from xdsl.ir import MLContext
from xdsl.pattern_rewriter import *
from io import StringIO

class CallableRewritePattern(RewritePattern):
    """
    Extension of RewritePattern to get an interface we can just call and which 
    returns the newly created Operation
    """
    @abstractmethod
    def __call__(self, op: Operation, rewriter: PatternRewriter) -> Operation:
        ...

    def match_and_rewrite(self, op : Operation, rewriter: PatternRewriter):
        self.__call__(op, rewriter)


def rewrite_and_compare(prog: str, expected_prog: str,
                        walker: PatternRewriteWalker):
    ctx = MLContext()
    builtin = Builtin(ctx)
    std = Std(ctx)
    arith = Arith(ctx)
    scf = Scf(ctx)

    parser = Parser(ctx, prog)
    module = parser.parse_op()

    walker.rewrite_module(module)
    file = StringIO("")
    printer = Printer(stream=file)
    printer.print_op(module)
    assert file.getvalue().strip() == expected_prog.strip()


def test_initial():
    """Test a simple non-recursive rewrite"""

    prog = \
"""module() {
%0 : !i32 = arith.constant() ["value" = 42 : !i32]
%1 : !i32 = arith.addi(%0 : !i32, %0 : !i32)
}"""

    expected = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 43 : !i32]
  %1 : !i32 = arith.addi(%0 : !i32, %0 : !i32)
}"""

    class RewriteConst(RewritePattern):

        def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter):
            if isinstance(op, Constant):
                new_constant = Constant.from_int_constant(43, i32)
                rewriter.replace_matched_op([new_constant])


    rewrite_and_compare(
        prog, expected,
        PatternRewriteWalker(RewriteConst(), apply_recursively=False))


def test_call_interface():

    prog = \
"""module() {
%0 : !i32 = arith.constant() ["value" = 42 : !i32]
%1 : !i32 = arith.addi(%0 : !i32, %0 : !i32)
}"""

    expected = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 43 : !i32]
  %1 : !i32 = arith.addi(%0 : !i32, %0 : !i32)
}"""

    class RewriteConst(CallableRewritePattern):

        def __call__(self, op: Operation, rewriter: PatternRewriter) -> Operation:
            if isinstance(op, Constant):
                new_constant = Constant.from_int_constant(43, i32)
                rewriter.replace_matched_op([new_constant])


    rewrite_and_compare(
        prog, expected,
        PatternRewriteWalker(RewriteConst(), apply_recursively=False))


def test_rewrite_return_value():

    prog = \
"""module() {
%0 : !i32 = arith.constant() ["value" = 42 : !i32]
%1 : !i32 = arith.addi(%0 : !i32, %0 : !i32)
}"""

    expected = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 43 : !i32]
  %1 : !i32 = arith.addi(%0 : !i32, %0 : !i32)
}"""

    class CreateConst(CallableRewritePattern):
        def __call__(self, op: Operation, rewriter: PatternRewriter) -> Operation:
            if isinstance(op, Constant):
                new_constant = Constant.from_int_constant(43, i32)
                return new_constant


    class RewriteConst(CallableRewritePattern):

        def __call__(self, op: Operation, rewriter: PatternRewriter) -> Operation:
            if isinstance(op, Constant):
                new_constant = CreateConst()(op, rewriter)
                rewriter.replace_matched_op([new_constant])
                return new_constant


    rewrite_and_compare(
        prog, expected,
        PatternRewriteWalker(RewriteConst(), apply_recursively=False))


def test_two_consts():

    prog = \
"""module() {
%0 : !i32 = arith.constant() ["value" = 42 : !i32]
%1 : !i32 = arith.addi(%0 : !i32, %0 : !i32)
}"""

    expected = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 43 : !i32]
  %1 : !i32 = arith.constant() ["value" = 43 : !i32]
  %2 : !i32 = arith.addi(%0 : !i32, %0 : !i32)
}"""

    class RewriteConst(CallableRewritePattern):

        def __call__(self, op: Operation, rewriter: PatternRewriter) -> Operation:
            if isinstance(op, Constant):
                new_constant0 = Constant.from_int_constant(43, i32)
                new_constant1 = Constant.from_int_constant(43, i32)
                # rewriter.insert_op_after(new_constant1, op) 
                # rewriter.insert_op_after(op, new_constant1)
                # both do not work, but should. Instead:
                rewriter.insert_op_after_matched_op(new_constant1)
                rewriter.replace_matched_op([new_constant0])
                return new_constant0


    rewrite_and_compare(
        prog, expected,
        PatternRewriteWalker(RewriteConst(), apply_recursively=False))


def test_seq():

    prog = \
"""module() {
%0 : !i32 = arith.constant() ["value" = 42 : !i32]
%1 : !i32 = arith.addi(%0 : !i32, %0 : !i32)
}"""

    expected = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 43 : !i32]
  %1 : !i32 = arith.constant() ["value" = 43 : !i32]
  %2 : !i32 = arith.addi(%0 : !i32, %0 : !i32)
}"""

    @dataclass
    class Seq(CallableRewritePattern):
        s1: CallableRewritePattern
        s2: CallableRewritePattern 

        def __call__(self, op: Operation, rewriter: PatternRewriter) -> Operation:
            intermediate = self.s1(op, rewriter)
            if (isinstance(intermediate, Operation)):   # i.e. was s1 successful
                # I have to call insert on the rewriter here or I lose the handle to it. 
                # Inside rewrite s1 it is too early to decide whether I want to 
                # insert the newly created op somewhere or the matched op should
                # be replaced by it.
                rewriter.insert_op_after_matched_op(intermediate)
                return self.s2(intermediate, rewriter)


    class CreateConst(CallableRewritePattern):
        def __call__(self, op: Operation, rewriter: PatternRewriter) -> Operation:
            if isinstance(op, Constant):
                new_constant = Constant.from_int_constant(43, i32)
                return new_constant


    class RewriteConst(CallableRewritePattern):

        def __call__(self, op: Operation, rewriter: PatternRewriter) -> Operation:
            if isinstance(op, Constant):
                result = Seq(CreateConst(), CreateConst())(op, rewriter)
                rewriter.replace_matched_op([result])
                return result


    rewrite_and_compare(
        prog, expected,
        PatternRewriteWalker(RewriteConst(), apply_recursively=False))
