# Copyright (c) 2016 by cisco Systems (Inc)
#
# November 2016, Robert Wilton
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
import re

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
    
def add_substmt_canonical(parent_stmt, stmt):
    parent_stmt.substmts.append(stmt)
    parent_stmt.substmts = grammar.sort_canonical(parent_stmt.keyword, parent_stmt.substmts)
    
def fix_references(stmt, elements):
    for e in elements:
        stmt.arg = re.sub("(?:)(" + e + ")", stmt.i_module.i_prefix + ":" + e, stmt.arg)
    
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

    if keyword == 'module':
        # Change the module name.
        module_name = stmt.arg
        stmt.arg = module_name + '-state'
        
        # Find the module prefix.
        prefix_stmt = next(x for x in stmt.substmts if x.keyword == 'prefix')
        
        # Rename the prefix statement.
        prefix = prefix_stmt.arg
        prefix_stmt.arg = prefix + '-s'
        
        # Add an import statement back to the original module.
        import_stmt = Statement(stmt.top, stmt, stmt.pos, 'import', module_name)
        add_substmt_canonical(stmt, import_stmt)
        add_substmt_canonical(import_stmt, Statement(stmt.top, import_stmt, import_stmt.pos, 'prefix', prefix))
    
        
    if keyword == 'namespace':
        stmt.arg = stmt.arg + '-state'
    
    # Remove any feature statements, reference the original module feature instead.
    if keyword == 'feature':
        stmt.parent.substmts.remove(stmt)
        
    if keyword == 'if-feature':
        fix_references(stmt, stmt.i_module.i_features)
            
    # Remove any identity statements, reference the original identity instead.
    # Identity base won't matter because they are all removed.
    if keyword == 'identity':
        stmt.parent.substmts.remove(stmt)
        
    if keyword in ('must', 'when'):
        fix_references(stmt, stmt.i_module.i_identities)
            
    if keyword == 'type' and stmt.arg == 'identityref':
        base_stmt = next(x for x in stmt.substmts if x.keyword == 'base')
        fix_references(base_stmt, stmt.i_module.i_identities)
        
    # Remove any typedef statements, reference the original typedef instead.
    if keyword == 'typedef':
        stmt.parent.substmts.remove(stmt)
        
    if keyword == 'type':
        fix_references(stmt, stmt.i_module.i_typedefs)
            
    # Remove all config statements, only the top level config false is necessary.
    if keyword == 'config':
        stmt.parent.substmts.remove(stmt)
        
    if len(stmt.substmts) != 0:
        substmts = grammar.sort_canonical(stmt.keyword, stmt.substmts)
        for s in substmts:
            convert_stmt(ctx, s, level + 1)

    # Convert top level containers from "foo" to "foo-state", and mark it as config false.
    if keyword == 'container' and stmt.parent.keyword == 'module':
        if not stmt.arg.endswith('-state'):
            stmt.arg = stmt.arg + '-state'
            add_substmt_canonical(stmt, Statement(stmt.top, stmt, stmt.pos, 'config', 'false'))
            