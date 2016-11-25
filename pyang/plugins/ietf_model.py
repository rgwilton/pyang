# Copyright (c) 2016 by Matthew Green <mgreen89@gmail.com>
#
# Pyang plugin converting between IETF model formats.
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
from pyang.statements import Statement

"""@@@Module docstring"""

#import optparse
#import re

from pyang import plugin
from pyang import util
from pyang import grammar

def pyang_plugin_init():
    plugin.register_plugin(IetfModelPlugin())

class IetfModelPlugin(plugin.PyangPlugin):
    def setup_fmt(self, ctx):
        ctx.implicit_errors = True

    def add_opts(self, optparser):
        optparser.add_option("--ietf-to-split-state-tree", dest="ietf_combined_to_split",
                             action="store_true",
                             help="From a combined config/state YANG tree, generate an additional IETF state tree")

    def post_validate_ctx(self, ctx, modules):
        # Run the plugin here.
        module = modules[0]
        # TODO - Need to copy the original tree here. 
        convert_stmt(ctx, module, 0)
        pass
    
    
def convert_stmt(ctx, stmt, level):
    if ctx.opts.yang_remove_unused_imports and stmt.keyword == 'import':
        for p in stmt.parent.i_unused_prefixes:
            if stmt.parent.i_unused_prefixes[p] == stmt:
                return

    if util.is_prefixed(stmt.raw_keyword):
        (prefix, identifier) = stmt.raw_keyword
        keyword = prefix + ':' + identifier
    else:
        keyword = stmt.keyword

    if keyword == "module":
        stmt.arg = stmt.arg + '-state'
        
    if keyword == "namespace":
        stmt.arg = stmt.arg + '-state'


    # Convert top level "foo" container to "foo-state", and mark it as config false.
    if keyword == 'container' and stmt.parent.keyword == 'module':
        if not stmt.arg.endswith('-state'):
            stmt.arg = stmt.arg + '-state'
            stmt.substmts.append(Statement(stmt.top, stmt, stmt.pos, 'config', 'false'))
            # TODO - Walk down the tree removing any config true statements
            
    if keyword == 'config' and stmt.arg == 'true':
        stmt.parent.substmts.remove(stmt)
        
    if len(stmt.substmts) != 0:
        if ctx.opts.yang_canonical:
            substmts = grammar.sort_canonical(stmt.keyword, stmt.substmts)
        else:
            substmts = stmt.substmts
        for s in substmts:
            convert_stmt(ctx, s, level + 1)

    """kwd_class = get_kwd_class(stmt.keyword)
    if ((level == 1 and
         kwd_class != prev_kwd_class and kwd_class != 'extension') or
        stmt.keyword in _keyword_with_trailing_newline):
        fd.write('\n')

    if keyword == '_comment':
        emit_comment(stmt.arg, fd, indent)
        return
    
    # Are we in a top level grouping, then don't expand 'uses'
    # Not doing the right thing.
    s = stmt
    in_grouping = False
    while hasattr(s, 'parent'):
        if hasattr(s, 'keyword') and s.keyword == 'grouping':
            in_grouping = True
        s = s.parent

    if ctx.opts.yang_expand_groupings and keyword == 'uses' and (within_uses or not in_grouping):
        fd.write ("\n" + indent + "// Expanded 'uses")
        emit_arg(stmt, fd, indent, indentstep)
        fd.write("'\n")
        for s in stmt.i_grouping.substmts:
            # Throw out the grouping description statement because it just
            # clutters the output
            if s.keyword != 'description':
                emit_stmt(ctx, s, fd, level, kwd_class,
                          indent, indentstep, True)
                kwd_class = get_kwd_class(s.keyword)
        return

    fd.write(indent + keyword)
    if stmt.arg != None:
        if keyword in grammar.stmt_map:
            (arg_type, _subspec) = grammar.stmt_map[keyword]
            if arg_type in _non_quote_arg_type:
                fd.write(' ' + stmt.arg)
            else:
                emit_arg(stmt, fd, indent, indentstep)
        else:
            emit_arg(stmt, fd, indent, indentstep)
    if len(stmt.substmts) == 0:
        fd.write(';\n')
    else:
        fd.write(' {\n')
        if ctx.opts.yang_canonical:
            substmts = grammar.sort_canonical(stmt.keyword, stmt.substmts)
        else:
            substmts = stmt.substmts
        if level == 0:
            kwd_class = 'header'
        for s in substmts:
            emit_stmt(ctx, s, fd, level + 1, kwd_class,
                      indent + indentstep, indentstep, within_uses)
            kwd_class = get_kwd_class(s.keyword)
        fd.write(indent + '}\n')"""
