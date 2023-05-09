from __future__ import annotations
from abc import ABCMeta, abstractmethod
from typing import Any, Union
## Parse tree nodes for the Calc language
import re
import sys
import importlib
import builtins

context: dict[str,object] = {}
verbose = False
protected_names = ["set", "call", "new", "quit", "exit", "import"]

# The exception classes from the notes.
class GroveException(Exception): pass
class GroveParseException(GroveException): pass
class GroveEvalException(GroveException): pass

# Command Base Class (superclass of expressions and statements)
class Command(object):
    @abstractmethod
    def __init__(self): pass
    @abstractmethod
    def eval(self) -> Any: pass
    @staticmethod
    def parse(s: str) -> Command:
        """Factory method for creating Command subclasses from lines of code"""
        # the command should split the input into tokens based on whitespace
        tokens: list[str] = s.strip().split()
        # a command must be either a statement or an expression
        try:
            # first try to parse the command as a statement
            return Statement.parse(tokens)
        except GroveParseException as e:
            if verbose: print(e)
        try:
            # if it is not a statement, try an expression
            return Expression.parse(tokens)
        except GroveParseException as e:
            if verbose: print(e)
        raise GroveParseException(f"Unrecognized Command: {s}")

# Expression Base Class (superclass of Num, Name, StringLiteral, etc.)
class Expression(Command):
    @abstractmethod
    def __init__(self): pass
    @abstractmethod
    def eval(self) -> int: pass
    @classmethod
    def parse(cls, tokens: list[str]) -> Expression:
        """Factory method for creating Expression subclasses from tokens"""
        # get a list of all the subclasses of Expression
        subclasses: list[type[Expression]] = cls.__subclasses__()
        # try each subclass in turn to see if it matches the pattern
        for subclass in subclasses:
            try: 
                return subclass.parse(tokens)
            except GroveParseException as e:
                if verbose: print(e)
        # if none of the subclasses parsed successfully raise an exception
        raise GroveParseException(f"Unrecognized Expression: {' '.join(tokens)}")
    @staticmethod
    def match_parens(tokens: list[str]) -> int:
        """Searches tokens beginning with ( and returns index of matching )"""
        # ensure tokens is such that a matching ) might exist
        if len(tokens) < 2: raise GroveParseException("Expression too short")
        if tokens[0] != '(': raise GroveParseException("No opening ( found")
        # track the depth of nested ()
        depth: int = 0
        for i,token in enumerate(tokens):
            # when a ( is found, increase the depth
            if token == '(': depth += 1
            # when a ) is found, decrease the depth
            elif token == ')': depth -= 1
            # if after a token the depth reaches 0, return that index
            if depth == 0: return i
        # if the depth never again reached 0 then parens do not match
        raise GroveParseException("No closing ) found")
     
   

# Statement Base Class (superclass of Assign, Terminate, and Import)
class Statement(Command):
    @abstractmethod
    def __init__(self): pass
    @abstractmethod
    def eval(self) -> None: pass
    @classmethod
    def parse(cls, tokens: list[str]):
        """Factory method for creating Statement subclasses from methods"""
        subclasses: list[type[Statement]] = cls.__subclasses__()
        for subclass in subclasses:
            try:
                return subclass.parse(tokens)
            except GroveParseException as e:
                if verbose: print(e)
        # if none of the subclasses parsed successfully raise an exception
        raise GroveParseException(f"Unrecognized Statement: {' '.join(tokens)}")


# -----------------------------------------------------------------------------
# Implement each of the following parse tree nodes for the Grove language
# -----------------------------------------------------------------------------

class Number(Expression):
    def __init__(self, num: int):
        self.num = num
    def eval(self) -> int:
        return self.num
    def __eq__(self, other: Any) -> bool:
        return (isinstance(other, Number) and other.num == self.num)
    @staticmethod
    def parse(tokens: list[str]) -> Number:
        """Factory method for creating Number expressions from tokens"""
        # 0. ensure there is exactly one token
        if len(tokens) != 1:
            raise GroveParseException("Wrong number of tokens for Number")
        # 1. ensure that all characters in that token are digits
        if not tokens[0].isdigit():
            raise GroveParseException("Numbers can only contain digits")
        # if this point is reached, this is a valid Number expression
        return Number(int(tokens[0]))

class StringLiteral(Expression):
    def __init__(self, string: str):
        self.string = string
    def eval(self) -> str:
        return self.string
    def __eq__(self, other: Any) -> bool:
        return (isinstance(other, StringLiteral) and other.string == self.string)
    @staticmethod
    def parse(tokens: list[str]) -> StringLiteral:
        """Factory method for creating StringLiteral expressions from tokens"""
        # 1. Ensure there is exactly one token
        if len(tokens) != 1:
            raise GroveParseException("Wrong number of tokens for StringLiteral")
        # 2. Ensure StringLiteral begins and ends with quotation marks
        if tokens[0][0] != '"' or tokens[0][tokens[0].__len__()] != '"':
            raise GroveParseException("StringLiteral does not begin and end with quotations")
        # 3. Ensure StringLiteral does not contain any extra quotations or whitespace
        if '"' in tokens[0][1:-1] or any(c.isspace() for c in tokens[0]):
            raise GroveParseException("Illegal character in StringLiteral")
        return StringLiteral(str(tokens[0]))

class Object(Expression):
    pass
  
class Call(Expression):
    def __init__(self, object: Name, method: Name, expr: list[Expression]):
        self.object = object
        self.method = method
        self.expr = expr
    def eval(self):
        if self.object not in context:
            raise GroveEvalException(f"Specified object {self.object} does not exist")
        object = context[self.object.name]
        if (not any(mn == self.method.name for mn in dir(object))):
            raise GroveEvalException(f"The object {self.object.name} does not have a method named {self.method.name}")
        values = [e.eval() for e in self.expr]
        try:
            res = getattr(object, self.method.name)(*values)
        except TypeError as e:
            raise GroveEvalException(f"The object {self.object.name}'s method {self.method.name} was called incorrectly.\n{e}")
        except Exception as e:
            raise GroveEvalException(f"An error occured while evaluating {self.object.name}'s method {self.method.name}.\n{e}")
        return res
    @classmethod
    def parse(cls, tokens: list[str]) -> Expression:
        if (len(tokens) < 5):
            raise GroveParseException(f"{' '.join(tokens)} does not have enough tokens for a call statement.")
        if (tokens[0] != 'call'):
            raise GroveParseException(f"{' '.join(tokens)} does not begin with 'call'.")
        closingparens = Expression.match_parens(tokens[2:]) + 2
        if (closingparens < 5):
            raise GroveParseException(f"{' '.join(tokens)} does not have enough tokens for a call statement between parantheses.")
        try:
            obj = Name.parse([tokens[2]])
        except:
            raise GroveParseException("No object name found for Call expression")
        try:
            met = Name.parse([tokens[3]])
        except:
            raise GroveParseException("No method name found for Call expression")
        expr: list[Expression] = list()
        start = 4
        for i in [i + start + 1 for i in range(closingparens - start)]:
            hasstatement = False
            try:
                Statement.parse(tokens[start:i])
                hasstatement = True
            except GroveParseException:
                try:
                    expr.append(Expression.parse(tokens[start:i]))
                    start = i + 1
                except GroveParseException:
                    continue
            if hasstatement:
                raise GroveParseException(f"Attempted to pass a statement {' '.join(tokens[start:i])} as an expression.")
            
        return Call(obj, met, expr)
        
class Addition(Expression):
    #TODO: Implement node for + statements   
    pass


class Name(Expression):
    def __init__(self, name: str):
        self.name = name
    def eval(self) -> object:
        try: return context[self.name]
        except KeyError: raise GroveParseException(f"{self.name} is undefined")
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Name) and self.name == other.name
    @staticmethod
    def parse(tokens: list[str]) -> Name:
        """Factory method for creating Name expressions from tokens"""
        if len(tokens) != 1:
            raise GroveParseException("Wrong number of tokens for Name")
        if not tokens[0].replace('_', 'a').isalnum():
            raise GroveParseException("Name must contain only alphanumeric characters")
        if not tokens[0][0].isalpha or tokens[0][0] == '_':
            raise GroveParseException("Name must start with an alphabetic character (or _)")
        if tokens[0] in protected_names:
            raise GroveParseException(f"Name {tokens[0]} is a reserved word")
        return Name(tokens[0])

class Assignment(Expression):
    def __init__(self, name: Name, value: Expression):
        self.name = name
        self.value = value
    def eval(self) -> None:
        value = self.value.eval()
        context[self.name.name] = (type(value), value)
    def __eq__(self, other: Any):
        return (isinstance(other, Assignment) and
        self.name == other.name and
        self.value == other.value)
    @staticmethod
    def parse(tokens: list[str]) -> Assignment:
        """Factory method for creating Assignment commands from tokens"""
        # check to see if this string matches the pattern for set
        # 0. ensure there are enough tokens for this to be a set statement
        if len(tokens) < 4:
            raise GroveParseException("Statement too short for Assignment")
        # 1. ensure that the very first token is "set" otherwise throw Exception
        if tokens[0] != 'set': 
            raise GroveParseException("Assignment statements must begin with 'set'")
        # 2. ensure that the next token is a valid Name
        try:
            name: Name = Name.parse([tokens[1]])
        except GroveParseException:
            raise GroveParseException("No name found for Assignment statement")
        # 3. ensure that the next token is an '='
        if tokens[2] != '=':
            raise GroveParseException("Assignment statement requires '='")
        # 4. ensure the remaining tokens represent an expression
        try:
            value: Expression = Expression.parse(tokens[3:])
        except GroveParseException:
            raise GroveParseException("No value found for Assignment statement")
        # if this point is reached, this is a valid Set statement
        return Assignment(name, value)

class Import(Expression):
    # TODO: Implement node for "import" statements
    pass

class Terminate(Statement):
    def __init__(self):
        pass
    def eval(self) -> None:
        sys.exit()
    @staticmethod
    def parse(tokens) -> Terminate:
        if len(tokens) != 1:
            raise GroveParseException("Wrong number of tokens for terminate")
        if tokens[0] != "quit" and tokens[0] != "exit":
            raise GroveParseException("Terminate statements must be either \"quit\" or \"set\"")
        return Terminate()
