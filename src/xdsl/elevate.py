from __future__ import annotations
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Union, Tuple

from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Operation, OpResult, Region, Block, BlockArgument, Attribute
from xdsl.rewriter import Rewriter
from xdsl.pattern_rewriter import RewritePattern
from xdsl.printer import Printer

@dataclass
class RewriteResult:
    result: Optional[Operation, str]

    def flatMapSuccess(self, s: Strategy, rewriter: Rewriter) -> RewriteResult:
        if (not isinstance(self.result, Operation)):
            return self
        return s(self.result, rewriter)

    def flatMapFailure(self, f: Callable) -> RewriteResult:
        if (not isinstance(self.result, Operation)):
            return f()
        return self


def success(op: Operation):
    return RewriteResult(op)

def failure(errorMsg: str):
    return RewriteResult(errorMsg)


class Strategy(RewritePattern):
    @abstractmethod
    def impl(self, op: Operation, rewriter: PatternRewriter) -> RewriteResult:
        ...

    def __call__(self, op: Operation, rewriter: PatternRewriter) -> RewriteResult:
        return self.impl(op, rewriter)

    def match_and_rewrite(self, op : Operation, rewriter: PatternRewriter):
        """Keeping the original interface"""
        self.impl(op, rewriter)


class id(Strategy):
    def impl(self, op: Operation, rewriter: PatternRewriter) -> RewriteResult:
        return success(op)


class fail(Strategy):
    def impl(self, op: Operation, rewriter: PatternRewriter) -> RewriteResult:
        return failure("fail Strategy applied")


@dataclass
class debug(Strategy):
    # debugMsg: str

    def impl(self, op: Operation, rewriter: PatternRewriter) -> RewriteResult:
        printer = Printer()
        printer.print_op(op)
        return success(op)


@dataclass
class seq(Strategy):
    s1: Strategy
    s2: Strategy

    def impl(self, op: Operation, rewriter: PatternRewriter) -> RewriteResult:
        rr = self.s1(op, rewriter)
        return rr.flatMapSuccess(self.s2, rewriter)


@dataclass
class leftChoice(Strategy):
    s1: Strategy
    s2: Strategy

    def impl(self, op: Operation, rewriter: PatternRewriter) -> RewriteResult:
        return self.s1(op, rewriter).flatMapFailure(lambda : self.s2(op, rewriter))


@dataclass
class try_(Strategy):
    s: Strategy

    def impl(self, op: Operation, rewriter: PatternRewriter) -> RewriteResult:
        return leftChoice(self.s, id())(op, rewriter)


@dataclass
class one(Strategy):
    s: Strategy

    def impl(self, op: Operation, rewriter: PatternRewriter) -> RewriteResult:
        if isinstance(op, ModuleOp):
            module: ModuleOp = op
            return self.s(module.ops[0], rewriter)
        for operand in reversed(op.operands):
            if (isinstance(operand, OpResult)):
                rr = self.s(operand.op, rewriter)
                if isinstance(rr.result, Operation):
                    return rr
        return failure("one traversal failure")


@dataclass
class topDown(Strategy):
    s: Strategy

    def impl(self, op: Operation, rewriter: PatternRewriter) -> RewriteResult:
        return leftChoice(self.s, one(topDown(self.s)))(op, rewriter)