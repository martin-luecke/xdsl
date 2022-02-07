from xdsl.dialects.builtin import *
from xdsl.parser import Parser
from xdsl.printer import Printer
from xdsl.dialects.std import *
from xdsl.dialects.arith import *

test_prog = """
module() {
  builtin.func() ["sym_name" = "test", "type" = !fun<[], []>, "sym_visibility" = "private"]
  {

    %7 : !i1 = arith.constant() ["value" = 0 : !i1]
    %8 : !i1 = arith.constant() ["value" = 1 : !i1]
    %9 : !i1 = arith.andi(%7 : !i1, %8 : !i1)
    %10 : !i1 = arith.ori(%7 : !i1, %8 : !i1)
    %11 : !i1 = arith.xori(%7 : !i1, %8 : !i1)
  }

  builtin.func() ["sym_name" = "rec", "type" = !fun<[!i32], [!i32]>, "sym_visibility" = "private"]
  {
  ^1(%20: !i32):
    %21 : !i32 = std.call(%20 : !i32) ["callee" = @rec] 
    std.return(%21 :!i32)
  }

  builtin.func() ["sym_name" = "br", "type" = !fun<[!i32], [!i32]>, "sym_visibility" = "private"]
  {
  ^2(%22: !i32):
    std.br(%22: !i32)(^2)
  }

  builtin.func() ["sym_name" = "cond_br", "type" = !fun<[!i32], [!i32]>, "sym_visibility" = "private"]
  {
  ^3(%23 : !i32):
    std.cond_br(%23 : !i32, %23 : !i32, %23 : !i32)(^3, ^4)
  ^4(%24 : !i32, %25 : !i32):
    std.return(%23 : !i32)
  }
}
"""


def test_main():
    ctx = MLContext()
    builtin = Builtin(ctx)
    std = Std(ctx)
    arith = Arith(ctx)

    parser = Parser(ctx, test_prog)
    module = parser.parse_op()

    module.verify()
    printer = Printer()
    printer.print_op(module)
    print()

    print("Done")
