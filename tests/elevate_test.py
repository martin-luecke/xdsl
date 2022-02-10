from xdsl.dialects.scf import Scf, If

from xdsl.printer import Printer
from xdsl.dialects.builtin import Builtin, IntegerAttr, i32, i64
from xdsl.parser import Parser
from xdsl.dialects.std import Std
from xdsl.dialects.arith import Arith, Constant, Addi, Muli
from xdsl.ir import MLContext
from xdsl.pattern_rewriter import *
from xdsl.elevate import *
from io import StringIO

def parse(prog: str) -> ModuleOp():
    ctx = MLContext()
    builtin = Builtin(ctx)
    std = Std(ctx)
    arith = Arith(ctx)
    scf = Scf(ctx)

    parser = Parser(ctx, prog)
    module = parser.parse_op()

    return module


def compare(op: Operation, expected_prog: str):
    file = StringIO("")
    printer = Printer(stream=file)
    printer.print_op(op)
    print(file.getvalue().strip())
    print(expected_prog.strip())

    assert file.getvalue().strip() == expected_prog.strip()


def test_id():
    prog = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 42 : !i32]
}"""

    module = parse(prog)
    rr = id()(module, Rewriter())
    
    compare(rr.result, prog)


def test_fail():
    prog = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 42 : !i32]
}"""

    module = parse(prog)
    rr = fail()(module, Rewriter())
    assert rr.result == "fail Strategy applied"


def test_seq():
    prog = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 42 : !i32]
}"""

    module = parse(prog)
    rr = seq(id(), id())(module, Rewriter())
    compare(rr.result, prog)


def test_seq_fail():
    prog = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 42 : !i32]
}"""

    module = parse(prog)
    rr = seq(fail(), id())(module, Rewriter())
    assert rr.result == "fail Strategy applied"


@dataclass
class NewConstAfterConst(Strategy):
    """ 
    Rewrite matches on arith.constant and adds another arith.constant after it
    with the specified int value.
    """
    value: int

    def impl(self, op: Operation, rewriter: Rewriter) -> RewriteResult:
        if isinstance(op, Constant):
            new_constant = Constant.from_int_constant(self.value, i32)
            rew = PatternRewriter(op)
            rew.insert_op_after_matched_op(new_constant)
            return success(new_constant)
        return failure("could not match constant")


def test_topDown_insert_const():
    prog = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 42 : !i32]
}"""

    expected = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 42 : !i32]
  %1 : !i32 = arith.constant() ["value" = 1 : !i32]
}"""

    module = parse(prog)
    rr = topDown(NewConstAfterConst(1))(module, Rewriter())
    compare(module, expected)


def test_seq_insert_const():
    prog = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 42 : !i32]
}"""

    expected = \
"""module() {
  %0 : !i32 = arith.constant() ["value" = 42 : !i32]
  %1 : !i32 = arith.constant() ["value" = 1 : !i32]
  %2 : !i32 = arith.constant() ["value" = 2 : !i32]
}"""

    module = parse(prog)
    rr = topDown(seq(NewConstAfterConst(1), NewConstAfterConst(2)))(module, Rewriter())
    compare(module, expected)