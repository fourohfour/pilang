import sys
from enum import Enum

def terminate():
    print("Interpreter Terminated")
    sys.exit(1)

class NodeType(Enum):
    SEQ    = 100
    SCOPE  = 1
    RETURN = 11
    OP     = 2
    ASSIGN = 3
    CYCLE  = 4
    EXPR   = 5
    PREDICATE = 6
    LVALUE = 10
    VALUE  = 12

class Node:
    def __init__(self, lptr, i, parent, nt, scope_sig, val = None):
        self.lptr     = lptr
        self.i        = i
        self.parent   = parent
        self.nt       = nt
        self.val      = val
        self.scope_sig   = scope_sig
        self.children = []

    def add_child(self, child):
        self.children.append(child)

    def rec_repr(self, prog, indent):
        s = "{indent}[{nt} ({i}) {val}]\n".format(indent = "\t" * indent, nt = self.nt.name, i = self.i, val = str(self.val))
        for c in self.children:
            child = prog.node(c)
            s += child.rec_repr(prog, indent + 1)
        return s

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

class Program:
    def __init__(self):
        self.cur_lptr = 0
        self.nodes  = [Node(0, 0, -1, NodeType.SEQ, "0")]
        self.root_index    = 0
        self.cons_stack    = [0]
        self.active_stack  = [0]
        self.scope_stack   = [0]

    def set_lptr(self, lptr):
        self.cur_lptr = lptr

    def node(self, i):
        return self.nodes[i]

    def root(self):
        return self.node(self.root_index)

    def construct(self):
        return self.node(self.cons_stack[-1])

    def active(self):
        return self.node(self.active_stack[-1])

    def add_leaf(self, nt, val = None):
        scope_sig = ".".join(str(s) for s in self.scope_stack)
        n = Node(self.cur_lptr, len(self.nodes), self.active_stack[-1], nt, scope_sig, val)
        self.active().add_child(len(self.nodes))
        self.nodes.append(n)

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

    def conclude_active(self):
        val = self.active_stack.pop()
        if val == self.scope_stack[-1]:
            self.scope_stack.pop()
        return val

    def conclude_construct(self):
        construct = self.cons_stack.pop()
        while self.conclude_active() != construct:
            continue

    def rebase_construct(self):
        construct = self.cons_stack[-1]
        while self.active_stack[-1] != construct:
            self.conclude_active()


    def rebase_sequence(self):
        while self.node(self.active_stack[-1]).nt != NodeType.SEQ:
            if self.active_stack[-1] == self.cons_stack[-1]:
                self.cons_stack.pop()
            self.conclude_active()

    def __repr__(self):
        return "=-=-= Program =-=-=\n" + self.root().rec_repr(self, 0)

class TokenType(Enum):
    GNAME  = 1
    LNAME  = 2
    NUMBER = 3
    COLON  = 5
    LPAREN = 10
    RPAREN = 11
    LBRACK = 12
    RBRACK = 13
    PLUS   = 20
    MINUS  = 21
    AT     = 30

class Token:
    def __init__(self, tt, val, lptr):
        self.tt   = tt
        self.val  = val
        self.lptr = lptr

    def __repr__(self):
        return "({tt}:{val})".format(tt = self.tt.name, val = self.val)

class Interpreter:
    def __init__(self):
        self.lines   = []
        self.program = Program()

    def _err(self, lptr, message):
        print("Error: on Line {}".format(lptr + 1))
        print(">>> {}".format(self.lines[lptr].rstrip()))
        print(message + "\n")

    def _warn(self, lptr, message):
        print("Warning: on Line {}".format(lptr + 1))
        print(">>> {}".format(self.lines[lptr].rstrip()))
        print(message + "\n")

    def tokenise(self, lptr):
        tokmap = {'[' : TokenType.LBRACK,
                  ']' : TokenType.RBRACK,
                  '(' : TokenType.LPAREN,
                  ')' : TokenType.RPAREN,
                  '@' : TokenType.AT    ,
                  '+' : TokenType.PLUS  ,
                  '-' : TokenType.MINUS ,
                  ':' : TokenType.COLON }

        line = self.lines[lptr]
        toks = []

        search = 1
        gname  = 2
        lname  = 3
        number = 4

        mode = search

        builder = ""
        for c in line:
            if mode == gname:
                if c.isalnum() or c == '_':
                    builder += c
                    continue

                toks.append(Token(TokenType.GNAME, builder, lptr))
                builder = ""
                mode = search

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

            elif mode == number:
                if c.isdecimal():
                    builder += c
                    continue

                toks.append(Token(TokenType.NUMBER, int(builder), lptr))
                builder = ""
                mode = search

            if mode == search:
                if c.isspace():
                    continue

                if c in tokmap.keys():
                    toks.append(Token(tokmap[c], None, lptr))
                    continue

                if c.isalpha() or c == '_':
                    mode = gname
                    builder += c
                    continue

                if c == '\'':
                    mode = lname
                    continue

                if c.isdecimal():
                    mode = number
                    builder += c
                    continue

                self._err(lptr, "Bad character in program '{}'".format(c))
        return toks

    def parse(self, lptr, toks):
        prog = self.program
        prog.set_lptr(lptr)

        lvalue = 10
        assign = 11

        paren_contents = 20
        scope_sig      = 21

        expr      = 100
        end       = 900

        expect  = lvalue

        index = -1
        while (index + 1) < len(toks):
            index += 1
            tok = toks[index]
            if   expect == lvalue:
                if tok.tt in {TokenType.GNAME, TokenType.LNAME}:
                    prog.add_active(NodeType.ASSIGN)
                    prog.add_leaf(NodeType.LVALUE, val = tok)
                    expect = assign
                else:
                    self._err(lptr, "Expected assignment")
                    terminate()

            elif expect == assign:
                if tok.tt == TokenType.COLON:
                    prog.add_active(NodeType.EXPR)
                    expect = expr
                else:
                    self._err(lptr, "Expected assignment")
                    terminate()

            elif expect == expr:
                if tok.tt == TokenType.LPAREN:
                    expect = paren_contents
                    continue
                if tok.tt == TokenType.RPAREN:
                    prog.conclude_construct()

                if tok.tt == TokenType.LBRACK:
                    prog.add_active(NodeType.CYCLE, construct = True)
                    prog.add_active(NodeType.PREDICATE, val = prog.construct().i)
                    continue

                if tok.tt == TokenType.RBRACK:
                    prog.conclude_construct()
                    continue

                if tok.tt == TokenType.COLON:
                    if prog.construct().nt == NodeType.CYCLE:
                        prog.rebase_construct()
                        prog.add_active(NodeType.EXPR)
                        continue
                    else:
                        self._err(lptr, "Colon found in non-cyclic expression")
                        break

                if tok.tt in {TokenType.GNAME,
                              TokenType.LNAME,
                              TokenType.NUMBER}:
                    if index + 1 < len(toks):
                        if toks[index + 1].tt in {TokenType.PLUS, TokenType.MINUS}:
                            prog.add_active(NodeType.OP, val = toks[index + 1])
                            prog.add_leaf(NodeType.VALUE, val = tok)
                            index += 1
                            continue
                    prog.add_leaf(NodeType.VALUE, val = tok)
                    continue


            elif expect == paren_contents:
                if tok.tt == TokenType.AT:
                    prog.add_active(NodeType.SCOPE, construct = True)
                    expect = scope_sig
                    continue
                else:
                    prog.add_active(NodeType.EXPR, construct = True)
                    expect = expr
                    index -= 1
                    continue

            elif expect == scope_sig:
                if tok.tt == TokenType.GNAME:
                    prog.add_active(NodeType.RETURN, val = tok)
                    prog.add_active(NodeType.SEQ)
                    expect = end
                    continue

            elif expect == end:
                self._err(lptr, "Tokens found beyond expected EOL")
                break

            else:
                self._err(lptr, "Internal Parser Error: Uncovered expectation")
                terminate()

        prog.rebase_sequence()

    def feed(self, line):
        self.lines.append(line)
        lptr = len(self.lines) - 1
        toks = self.tokenise(lptr)
        self.parse(lptr, toks)

    def execute(self):
        global_names = {}
        stack = [ [[self.program.root()], {}] ]
        while stack:
            frame = stack[-1]
            while frame:
                node = to_exec.pop(0)
                if node.nt == NodeType.SEQ:
                    for s in node.children:
                        to_exec.append(self.program.node(s))

                if node.nt == NodeType.SCOPE:
                    stack.append([])

    def execute(self):
        nget = self.program.node

        scope_map = {"0": []}

        node_values = {}
        var_values  = {}

        to_exec = i.program.root().rec_list(i.program)
        jump_node = None
        while to_exec:
            node = to_exec.pop(0)
            if jump_node is not None:
                if node.i != jump_node:
                    continue
                else:
                    jump_node = None

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

            elif node.nt == NodeType.EXPR:
                node_values[node.i] = node_values[nget(node.children[0]).i]

            elif node.nt == NodeType.LVALUE:
                if node.val.val not in var_values:
                    var_values[node.val.val] = None
                    if node.val.tt == TokenType.LNAME:
                        if node.scope_sig not in scope_map:
                            scope_map[node.scope_sig] = [node.val.val]
                        else:
                            scope_map[node.scope_sig].append(node.val.val)

            elif node.nt == NodeType.ASSIGN:
                lname = nget(node.children[0]).val.val
                var_values[lname] = node_values[node.children[1]]

            elif node.nt == NodeType.OP:
                op1 = node_values[node.children[0]]
                op2 = node_values[node.children[1]]
                if node.val.tt == TokenType.PLUS:
                    node_values[node.i] = op1 + op2
                elif node.val.tt == TokenType.MINUS:
                    node_values[node.i] = op1 - op2

            elif node.nt == NodeType.RETURN:
                found_local = False
                for nameset in scope_map.values():
                    if node.val.val in nameset:
                        found_local = True
                        break

                if found_local:
                    node_values[node.i] = var_values[node.val.val]

                else:
                    print(scope_map)
                    self._err(node.lptr, "{} is not an in-scope local variable.".format(node.val.val))
                    terminate()

            elif node.nt == NodeType.SCOPE:
                node_values[node.i] = node_values[node.children[0]]
                if node.scope_sig in scope_map:
                    for var in scope_map[node.scope_sig]:
                        del var_values[var]
                    del scope_map[node.scope_sig]

            elif node.nt == NodeType.PREDICATE:
                node_values[node.i] = node_values[node.children[0]]
                if node_values[node.i] <= 0:
                    jump_node = node.val

            elif node.nt == NodeType.CYCLE:
                test = node_values[node.children[0]]

                if test <= 0:
                    if node.children[1] not in node_values:
                        node_values[node.i] = []
                else:
                    if node.i in node_values:
                        node_values[node.i].append(node_values[node.children[1]])
                    else:
                        node_values[node.i] = [node_values[node.children[1]]]

                    to_exec = node.rec_list(i.program) + to_exec

        print("Execution concluded")
        for var in var_values:
            print("{} : {}".format(var, var_values[var]))

i = Interpreter()
for line in sys.stdin:
    i.feed(line)

i.execute()
