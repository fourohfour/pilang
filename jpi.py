import sys
from enum import Enum


def terminate():
    print("Interpreter Terminated")
    sys.exit(1)

class NodeType(Enum):
    SEQ       = 10   # Sequence of statements
    SCOPE     = 11   # Scope for local variables
    RETURN    = 12   # First child of SCOPE; local to return
    OP        = 20   # Arithmatic Operation
    VALUE     = 21   # Some value (name or literal)
    ASSIGN    = 30   # An assignment
    LVALUE    = 31   # Left side value for an assignment
    CYCLE     = 40   # A Cycle
    CONDEX    = 50   # Conditional Expression
    IF        = 51   # If
    ELSE      = 52   # Else
    PREDICATE = 99   # Predicate
    EXPR      = 100  # An expression (potentially containing arith.)

class Node:
    def __init__(self, lptr, i, parent, nt, scope_sig, val = None):
        self.lptr     = lptr          # Line Pointer
        self.i        = i             # Node Index
        self.parent   = parent        # Parent Node Index
        self.nt       = nt            # Node Type
        self.val      = val           # Node Value
        self.scope_sig   = scope_sig  # Scope Signature
        self.children = []            # Child Nodes

    def add_child(self, child):
        self.children.append(child)

    # Recursively stringify this node and its children
    def rec_repr(self, prog, indent):
        s = "{indent}[{nt} ({i}) {val}]\n".format(indent = "\t" * indent, nt = self.nt.name, i = self.i, val = str(self.val))
        for c in self.children:
            child = prog.node(c)
            s += child.rec_repr(prog, indent + 1)
        return s

    # Recursively list this node and its children in order of dependance
    # A --|--B--|
    #     |     |-- C
    #     |     |-- D
    #     |--E
    # Yields [C, D, B, E, A]
    def rec_list(self, prog):
        l = [prog.node(child).rec_list(prog) for child in self.children]
        new_l = []
        for citems in l:
            for item in citems:
                new_l.append(item)
        new_l.append(self)
        return new_l

    def __repr__(self):
        return "({nt} ({i}) {val})".format(nt = self.nt.name, i = self.i, val = str(self.val))


# Both an IR for a program (as a semi-AST) and a store for parser state
class Program:
    def __init__(self):
        self.cur_lptr = 0
        self.nodes  = [Node(0, 0, -1, NodeType.SEQ, "0")]
        self.root_index    = 0
        self.cons_stack    = [0] # Constructs: Code structures using (), []
        self.active_stack  = [0] # Actives:    Nodes with ability to have children
        self.scope_stack   = [0] # Scopes:     Structures with own locals

    def set_lptr(self, lptr):
        self.cur_lptr = lptr

    # Get Node from Index
    def node(self, i):
        return self.nodes[i]

    # Get Root Node
    def root(self):
        return self.node(self.root_index)

    # Get current Construct
    def construct(self):
        return self.node(self.cons_stack[-1])

    # Get current Active
    def active(self):
        return self.node(self.active_stack[-1])

    # Add leaf node to current Active
    def add_leaf(self, nt, val = None):
        scope_sig = ".".join(str(s) for s in self.scope_stack)
        n = Node(self.cur_lptr, len(self.nodes), self.active_stack[-1], nt, scope_sig, val)
        self.active().add_child(len(self.nodes))
        self.nodes.append(n)

    # Create Active child on current Active
    def add_active(self, nt, val = None, construct = False):
        if nt == NodeType.SCOPE:
            self.scope_stack.append(len(self.nodes))

        scope_sig = ".".join(str(s) for s in self.scope_stack)

        n = Node(self.cur_lptr, len(self.nodes), self.active_stack[-1], nt, scope_sig, val)
        self.active().add_child(len(self.nodes))
        self.nodes.append(n)
        self.active_stack.append(n.i)

        if construct:
            self.cons_stack.append(n.i)

    # Shift back up the stack by 1 active
    def conclude_active(self):
        val = self.active_stack.pop()
        if val == self.scope_stack[-1]:
            self.scope_stack.pop()
        if val == self.cons_stack[-1]:
            self.cons_stack.pop()
        return val

    # Shift up the stack until reaching an active satisfying a condition
    def rebase_when(self, checkf):
        while not checkf(self.node(self.active_stack[-1])):
            self.conclude_active()

    # Shift up the stack, with the last shifted active satsifying a condition
    def conclude_when(self, checkf):
        self.rebase_when(checkf)
        self.conclude_active()

    # Conclude the current construct
    def conclude_construct(self):
        self.conclude_when(lambda node: node.i == self.cons_stack[-1])

    # Rebase the current construct (make it the active)
    def rebase_construct(self):
        self.rebase_when(lambda node: node.i == self.cons_stack[-1])

    # Rebase the current sequence (make it the active)
    def rebase_sequence(self):
        self.rebase_when(lambda node: node.nt == NodeType.SEQ)

    # Rebase to a grouping when at a linebreak (to the first construct or sequence)
    def rebase_lineend(self):
        self.rebase_when(lambda node: node.nt == NodeType.SEQ or node.i == self.cons_stack[-1])

    def __repr__(self):
        return self.root().rec_repr(self, 0).strip()

class TokenType(Enum):
    GNAME  = 1    # Global Name
    LNAME  = 2    # Local Name
    NUMBER = 3    # Number Literal
    COLON  = 5    # :
    LPAREN = 10   # (
    RPAREN = 11   # )
    LBRACK = 12   # [
    RBRACK = 13   # ]
    PLUS   = 20   # +
    MINUS  = 21   # -
    AT     = 30   # @
    QUOI   = 40   # ?
    SEMI   = 41   # ;


class Token:
    def __init__(self, tt, val, lptr):
        self.tt   = tt    # Token Type
        self.val  = val   # Token Value
        self.lptr = lptr  # Token Line Pointer

    def __repr__(self):
        return "({tt}:{val})".format(tt = self.tt.name, val = self.val)

# Interpreter encapsulates an execution of the program
class Interpreter:
    def __init__(self, args):
        self.args    = args       # A cleaned up list of program arguments
        self.lines   = []         # Raw Program Lines
        self.program = Program()  # Program object

    # Log an Error
    def _err(self, lptr, message):
        print("Error: on Line {}".format(lptr + 1))
        print(">>> {}".format(self.lines[lptr].rstrip()))
        print(message + "\n")

    # Log a Warning
    def _warn(self, lptr, message):
        print("Warning: on Line {}".format(lptr + 1))
        print(">>> {}".format(self.lines[lptr].rstrip()))
        print(message + "\n")

    # Log a horisontal rule
    def _rule(self, nl=False):
        if nl:
            print("\n=-=-=-=-=-=-=-=-=-=")
        else:
            print("=-=-=-=-=-=-=-=-=-=")

    # Tokenise a line of the program
    def tokenise(self, lptr):
        # Mapping for single char tokens
        tokmap = {'[' : TokenType.LBRACK,
                  ']' : TokenType.RBRACK,
                  '(' : TokenType.LPAREN,
                  ')' : TokenType.RPAREN,
                  '@' : TokenType.AT    ,
                  '+' : TokenType.PLUS  ,
                  '-' : TokenType.MINUS ,
                  ':' : TokenType.COLON ,
                  '?' : TokenType.QUOI  ,
                  ';' : TokenType.SEMI  ,}

        line = self.lines[lptr]
        toks = []

        # Tokeniser consumption modes
        search = 1
        gname  = 2
        lname  = 3
        number = 4

        mode = search

        builder = ""
        for c in line:
            # Tokeniser building a Global Name
            if mode == gname:
                if c.isalnum() or c == '_':
                    builder += c
                    continue

                toks.append(Token(TokenType.GNAME, builder, lptr))
                builder = ""
                mode = search
                # Breaking characters fall through
                # triggering later `mode == search` block

            # Tokeniser building a Local Name
            elif mode == lname:
                if c.isalnum() or c == '_':
                    builder += c
                    continue

                toks.append(Token(TokenType.LNAME, builder, lptr))
                builder = ""
                mode = search

                if c != '\'':
                    self._err(lptr, "Bad character in local identifier '{}'".format(c))
                else:
                    continue

            # Tokeniser building a number
            elif mode == number:
                if c.isdecimal():
                    builder += c
                    continue

                toks.append(Token(TokenType.NUMBER, int(builder), lptr))
                builder = ""
                mode = search
                # Breaking characters fall through

            # Searching freely for token
            if mode == search:
                # Chew whitespace
                if c.isspace():
                    continue

                # Deal with single char tokens
                if c in tokmap.keys():
                    toks.append(Token(tokmap[c], None, lptr))
                    continue

                # Begin to build Global Names.
                if c.isalpha() or c == '_':
                    mode = gname
                    builder += c
                    continue

                # Begin to build Local Names
                if c == '\'':
                    mode = lname
                    continue

                # Begin to build Numbers
                if c.isdecimal():
                    mode = number
                    builder += c
                    continue

                # Handle special output variable
                if c == '!':
                    toks.append(Token(TokenType.GNAME, '!', lptr))
                    continue

                self._err(lptr, "Bad character in program '{}'".format(c))
        return toks

    def parse(self, lptr, toks):
        prog = self.program
        prog.set_lptr(lptr)

        # Parser Expectation States
        initial        = 10    # Expect the start of a line
        assign         = 11    # Expect an assignment colon
        paren_contents = 20    # Expect contents of ()
        scope_ret      = 21    # Expect a scope return to follow @
        expr_val       = 100   # Expect a value in an expression
        expr_op        = 101   # Expect an operation in an expression
        end            = 900   # Expect newline

        expect  = initial

        # Iterate through tokens

        index = -1
        while (index + 1) < len(toks):
            index += 1
            tok = toks[index]

            if   expect == initial:
                # A line can start with a name in the case of an assignment
                if tok.tt in {TokenType.GNAME, TokenType.LNAME}:
                    prog.add_active(NodeType.ASSIGN)
                    prog.add_leaf(NodeType.LVALUE, val = tok)
                    expect = assign
                    continue

                # It may also start with ')' or ']' - but we want this to be handled by expr
                # Fallthrough to `expect == expr`
                if tok.tt in {TokenType.RPAREN, TokenType.RBRACK}:
                    expect = expr_op
                else:
                    self._err(lptr, "Malformed line")
                    terminate()

            if expect == assign:
                # Only a COLON can be `assign` (succeed an LVALUE)
                if tok.tt == TokenType.COLON:
                    prog.add_active(NodeType.EXPR)
                    expect = expr_val
                    continue

                else:
                    self._err(lptr, "Expected assignment")
                    terminate()

            if expect == expr_val:
                # Handle start of condexes
                if tok.tt == TokenType.QUOI:
                    prog.add_active(NodeType.CONDEX, construct = True)
                    prog.add_active(NodeType.IF    )
                    prog.add_active(NodeType.PREDICATE,
                                    val = (lambda ev: ev > 0 ,
                                           prog.construct().i,
                                           prog.active().i))
                    prog.add_active(NodeType.EXPR)
                    continue

                # Handle Values
                if tok.tt in {TokenType.GNAME,
                              TokenType.LNAME,
                              TokenType.NUMBER}:

                    # ! manifests as a GNAME but can only be used as an LVALUE
                    if tok.val == "!":
                        self._err(lptr, "Cannot use output variable '!' as value.")
                        break

                    # Special cases aside we can just add as a leaf
                    prog.add_leaf(NodeType.VALUE, val = tok)
                    expect = expr_op
                    continue

                if tok.tt == TokenType.LPAREN:
                    expect = paren_contents
                    continue

                if tok.tt == TokenType.LBRACK:
                    prog.add_active(NodeType.CYCLE, construct = True)
                    prog.add_active(NodeType.PREDICATE,
                                    val = (lambda ev: ev <= 0, prog.construct().i))
                    prog.add_active(NodeType.EXPR)
                    continue


            if expect == expr_op:
                # Handle Operators
                # Note that arithmatic parsing is handled during execution
                if tok.tt in {TokenType.PLUS, TokenType.MINUS}:
                    prog.add_leaf(NodeType.OP, val = tok)
                    expect = expr_val
                    continue

                # Brackets and Parens need to be handled - they cause `expect` changes
                implied_colon = False
                if tok.tt in {TokenType.LPAREN, TokenType.LBRACK}:
                    if prog.construct().nt in {NodeType.CYCLE, NodeType.CONDEX}:
                        self._warn(lptr, "Missing colon in construct")
                        index -= 1
                        implied_colon = True
                        expect = expr_val
                    else:
                        self._err(lptr, "Malformed Expression - Found '(' or '[' in bad position.")
                        terminate()

                if tok.tt == TokenType.RPAREN:
                    while prog.construct().nt == NodeType.CONDEX:
                        prog.conclude_construct()

                    if prog.construct().nt not in {NodeType.EXPR, NodeType.SCOPE}:
                        self._err(lptr, "Found ')' but next construct to close is not an expression or scope.")
                        terminate()

                    prog.conclude_construct()
                    continue


                if tok.tt == TokenType.RBRACK:
                    while prog.construct().nt == NodeType.CONDEX:
                        prog.conclude_construct()

                    if prog.construct().nt != NodeType.CYCLE:
                        self._err(lptr, "Found ']' but next construct to close is not a cycle.")
                        terminate()

                    prog.conclude_construct()
                    continue

                # Only allow a colon if we're at the top level of a CYCLE
                if tok.tt == TokenType.COLON or implied_colon:
                    if prog.construct().nt in {NodeType.CYCLE, NodeType.CONDEX}:
                        if prog.construct().nt == NodeType.CONDEX:
                            prog.rebase_when(lambda n: n.nt in {NodeType.IF, NodeType.ELSE})
                            if prog.active().nt == NodeType.ELSE:
                                self._err(lptr, "Cannot have predicate in else statement")
                                terminate()
                        else:
                            prog.rebase_construct()
                        prog.add_active(NodeType.EXPR)
                        expect = expr_val
                        continue
                    else:
                        self._err(lptr, "Colon found outside of cycle or conditional expression")
                        break

                if tok.tt == TokenType.QUOI:
                    if prog.construct().nt == NodeType.CONDEX:
                        prog.rebase_construct()
                        prog.add_active(NodeType.IF)
                        prog.add_active(NodeType.PREDICATE,
                                        val = (lambda ev: ev > 0 ,
                                               prog.construct().i,
                                               prog.active().i))
                        prog.add_active(NodeType.EXPR)
                        expect = expr_val
                        continue

                if tok.tt == TokenType.SEMI:
                    if prog.construct().nt == NodeType.CONDEX:
                        prog.rebase_construct()
                        prog.add_active(NodeType.ELSE)
                        prog.add_active(NodeType.EXPR)
                        expect = expr_val
                        continue

            if expect == paren_contents:
                # An '@' implies a scope
                if tok.tt == TokenType.AT:
                    prog.add_active(NodeType.SCOPE, construct = True)
                    expect = scope_ret
                    continue

                # Otherwise, just a normal expression
                # We decrement the index to allow `expect = expr_val` to handle it
                else:
                    prog.add_active(NodeType.EXPR, construct = True)
                    expect = expr_val
                    index -= 1
                    continue

            # The scope return value manifests as a GNAME
            # This is because quotes are elided
            # It's still semantically an LNAME
            if expect == scope_ret:
                if tok.tt == TokenType.GNAME:
                    prog.add_active(NodeType.RETURN, val = tok)
                    prog.add_active(NodeType.SEQ)
                    expect = end
                    continue

            # If the line has ended, the loop should already have broken!
            if expect == end:
                self._err(lptr, "Tokens found beyond expected EOL")
                break

            # This should never happen!
            self._err(lptr, "Internal Parser Error: Uncovered expectation")
            terminate()

        if expect not in {initial, end, expr_op}:
            self._warn(lptr, "weird expect at nl {}".format(expect))

        # Return to the nearest sequence or construct - concluding assignments etc.
        while prog.active().nt != NodeType.SEQ:
            if prog.active().nt == NodeType.ELSE:
                prog.conclude_construct()
            elif prog.active().i == prog.construct().i:
                break
            prog.conclude_active()

    # Lines are fed in one at a time, and are tokenised and parsed
    def feed(self, line):
        self.lines.append(line)
        lptr = len(self.lines) - 1
        toks = self.tokenise(lptr)
        self.parse(lptr, toks)

    # Execute the entire program
    def execute(self):
        nget = self.program.node

        # Mapping: Scope Signature -> [Local Variables]
        scope_map = {"0": []}

        # Nodes hold values that can propogate upwards
        node_values = {}

        # Variable values - both global and local
        var_values  = {}

        # Recursively generate a list of nodes to be executed
        to_exec = i.program.root().rec_list(i.program)

        # Set this to a node index to act as a goto
        jump_node = None

        # Continue executing nodes while any are left
        while to_exec:
            node = to_exec.pop(0)

            # If jump condition: skip until met
            if jump_node is not None:
                if node.i != jump_node:
                    continue
                else:
                    jump_node = None

            # VALUE nodes assume the values of their contents
            if node.nt == NodeType.VALUE:
                if node.val.tt == TokenType.GNAME:
                    if node.val.val in var_values:
                        node_values[node.i] = var_values[node.val.val]
                    else:
                        self._err(node.lptr, "Undefined global name {}".format(node.val.val))
                        terminate()

                elif node.val.tt == TokenType.LNAME:
                    if node.val.val in var_values:
                        node_values[node.i] = var_values[node.val.val]
                    else:
                        self._err(node.lptr, "Undefined local name {}".format(node.val.val))
                        terminate()

                elif node.val.tt == TokenType.NUMBER:
                    node_values[node.i] = node.val.val

            # Expressions evaluate to the value of their contents
            # Non-trivial expressions are parsed with the shunting-yard algorithm
            elif node.nt == NodeType.EXPR:
                if len(node.children) == 1:
                    node_values[node.i] = node_values[nget(node.children[0]).i]
                else:
                    VALUE = 1
                    OP    = 2

                    # Convert standard arithmatic expression to RPN

                    precedence = {TokenType.PLUS : 1, TokenType.MINUS: 1}
                    opstack  = []

                    # List of tuples: either (VALUE, value) or (OP, TokenType)
                    outqueue = []

                    for c in node.children:
                        child = nget(c)
                        if child.nt == NodeType.OP:
                            while len(opstack):
                                peek = opstack[-1]
                                if precedence[peek] >= precedence[child.val.tt]:
                                    outqueue.append((OP, opstack.pop()))
                                else:
                                    opstack.append(child.val.tt)
                                    break
                            if not len(opstack):
                                opstack.append(child.val.tt)
                        else:
                            outqueue.append((VALUE, node_values[c]))

                    while opstack:
                        outqueue.append((OP, opstack.pop()))

                    # Evaluate RPN expression

                    ptr = 0
                    while len(outqueue) > 1:
                        if ptr == len(outqueue):
                            self._err(node.lptr, "Malformed Arithmatic")
                            terminate()

                        # We shift past values to find operators
                        if outqueue[ptr][0] == VALUE:
                            ptr += 1
                            continue

                        # Can't evaluate an operator with less than two operands
                        if ptr < 2:
                            self._err(node.lptr, "Malformed Arithmatic")
                            terminate()

                        # Pull out the operator and two operands
                        op    = outqueue.pop(ptr)[1]
                        right = outqueue.pop(ptr - 1)[1]
                        left  = outqueue.pop(ptr - 2)[1]

                        result = None
                        if op == TokenType.PLUS:
                            result = left + right
                        elif op == TokenType.MINUS:
                            result = left - right

                        # Push the result back
                        outqueue.insert(ptr - 2, (VALUE, result))
                        ptr -= 1

                    # EXPR node assumes the lone value left on the queue
                    node_values[node.i] = outqueue[0][1]


            # LVALUES need to be initialised if they don't already exist
            # For locals (TokenType.LNAME), the scope is logged in the scope_map
            elif node.nt == NodeType.LVALUE:
                if node.val.val not in var_values and node.val.val != "!":
                    var_values[node.val.val] = None
                    if node.val.tt == TokenType.LNAME:
                        if node.scope_sig not in scope_map:
                            scope_map[node.scope_sig] = [node.val.val]
                        else:
                            scope_map[node.scope_sig].append(node.val.val)

            # Assignments fill out the var_values entry for the LNAME
            # '!' is handled seperately - the RVALUE is printed.
            elif node.nt == NodeType.ASSIGN:
                lname = nget(node.children[0]).val.val
                if lname == "!":
                    print(node_values[node.children[1]])
                else:
                    var_values[lname] = node_values[node.children[1]]

            # Return nodes propogate the specified value upwards
            elif node.nt == NodeType.RETURN:
                found_local = False
                for nameset in scope_map.values():
                    if node.val.val in nameset:
                        found_local = True
                        break

                if found_local:
                    node_values[node.i] = var_values[node.val.val]

                else:
                    self._err(node.lptr, "{} is not an in-scope local variable.".format(node.val.val))
                    terminate()

            # Scopes propogate the Return value upwards
            # They also clear their owned locals from node_values
            elif node.nt == NodeType.SCOPE:
                node_values[node.i] = node_values[node.children[0]]
                if node.scope_sig in scope_map:
                    for var in scope_map[node.scope_sig]:
                        del var_values[var]
                    del scope_map[node.scope_sig]

            # If the predicate value matches a test, it blocks until a specified node
            elif node.nt == NodeType.PREDICATE:
                result = node.val[0](node_values[node.children[0]])
                node_values[node.i] = result
                if result:
                    jump_node = node.val[1]
                elif len(node.val) > 2:
                    jump_node = node.val[2]

            elif node.nt == NodeType.CYCLE:
                # If the body never executed we need to propogate an empty list
                if node_values[node.children[0]]:
                    if node.i not in node_values:
                        node_values[node.i] = []

                # When test doesn't fail, the computed value gets pushed
                # The CYCLE's subtree is added to the to_exec stack
                else:
                    if node.i in node_values:
                        node_values[node.i].append(node_values[node.children[1]])
                    else:
                        node_values[node.i] = [node_values[node.children[1]]]

                    child_indexes = [c.i for c in node.rec_list(i.program) if c.i != node.i]
                    for ind in child_indexes:
                        if ind in node_values:
                            del node_values[ind]
                    to_exec = node.rec_list(i.program) + to_exec

            elif node.nt == NodeType.CONDEX:
                if node.i in node_values:
                    node_values[node.i] = node_values[node_values[node.i]]
                    continue

                for c in node.children:
                    block = nget(c)
                    if block.nt == NodeType.IF:
                        p = block.children[0]
                        if node_values[p]:
                            to_exec = nget(block.children[1]).rec_list(i.program) + [node] + to_exec
                            node_values[node.i] = block.children[1]
                            break

                    elif block.nt == NodeType.ELSE:
                        node_values[node.i] = node_values[block.i]

            elif node.nt == NodeType.ELSE:
                node_values[node.i] = node_values[node.children[0]]

        # Print globals on conclusion when --globals passed to program
        if "globals" in self.args:
            self._rule()

            for var in var_values:
                print("{} : {}".format(var, var_values[var]))

            self._rule()

if __name__ == "__main__":
    # Create the Interpreter, passing in the arguments
    i = Interpreter([a[2:].lower() for a in sys.argv[1:] if a.startswith("--")])

    # Tokenise and Parse lines one at a time
    for line in sys.stdin:
        i.feed(line)

    # Print semi-AST if requested by --ast
    if "ast" in i.args:
        i._rule()
        print(i.program)
        i._rule()

    # Execute program
    i.execute()
