# Copyright (c) 2017 by cisco Systems (Inc)
#
# January 2017, Robert Wilton
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
        optparser.add_option("--ietf-split-to-combined-tree", dest="ietf_split_to_combined",
                             action="store_true",
                             help="From an existing IETF split config/state tree, generate a single combined tree")
        optparser.add_option("--remove-state-nodes", dest="ietf_remove_state_nodes",
                             action="store_true",
                             help="Remove state nodes, rather than marking them deprecated")

    def post_validate_ctx(self, ctx, modules):
        IetfModelPlugin.remove_state = ctx.opts.ietf_remove_state_nodes
        if ctx.opts.ietf_split_to_combined:
            # Run the plugin here.
            module = modules[0]
            # TODO - Need to copy the original tree here. 
            convert_module(ctx, module)
    
def add_substmt_canonical(parent_stmt, stmt):
    parent_stmt.substmts.append(stmt)
    parent_stmt.substmts = grammar.sort_canonical(parent_stmt.keyword, parent_stmt.substmts)
    
def fix_references(stmt, elements):
    for e in elements:
        stmt.arg = re.sub("(?:)(" + e + ")", stmt.i_module.i_prefix + ":" + e, stmt.arg)
    
# Check that this is a config container (i.e. it isn't config false and doesn't end with -state)
def is_config_container(stmt):
    is_cfg_container = False
    
    if stmt.keyword == 'container' and not stmt.arg.endswith("-state"):
        stmts = [s for s in stmt.substmts if s.keyword == 'config' and s.arg == "false"]
        if len(stmts) == 0:
            is_cfg_container = True
           
    return (is_cfg_container)

# Check that this is a config container (i.e. it isn't config false and doesn't end with -state)
def is_state_container(stmt):
    is_state_container = False
    
    if stmt.keyword == 'container' and stmt.arg.endswith("-state"):
        stmts = [s for s in stmt.substmts if s.keyword == 'config' and s.arg == "false"]
        if len(stmts) == 1:
            is_state_container = True
           
    return (is_state_container)

# Check that this is an augment of a config container.
def is_config_augment(stmt):
    is_cfg_container = False
    
    if stmt.keyword == 'container' and not stmt.arg.endswith("-state"):
        stmts = [s for s in stmt.substmts if s.keyword == 'config' and s.arg == "false"]
        if len(stmts) == 0:
            is_cfg_container = True
           
    return (is_cfg_container)


# Check that this is an augment of a state container.
aug_check_pattern = re.compile("^(/[^/]+?)-state(/.*)$")
def is_state_augmentation(stmt):
    is_state_augmentation = False
    
    if stmt.keyword == 'augment' and aug_check_pattern.match(stmt.arg):
        is_state_augmentation = True
           
    return (is_state_augmentation)

def matching_cfg_augment(state_arg):
    m = aug_check_pattern.match(state_arg)
    cfg_str = m.group(1) + m.group(2)
    return cfg_str

def matches_cfg_augment(cfg_stmt, state_aug_stmt):
    return (cfg_stmt.keyword == 'augment' and
            cfg_stmt.arg == matching_cfg_augment(state_aug_stmt.arg))

#
# Check whether a config and state statement match and should not be copied across.
#
def is_matching_stmt(cfg_stmt, state_stmt):
    matching = False
    if (state_stmt.keyword == cfg_stmt.keyword
        and (state_stmt.keyword in ['description', 'presence']
             or cfg_stmt.arg == state_stmt.arg)):
        matching = True
    return (matching)
    
# Peform any other required fix up
if_state_ref_pattern = re.compile("^([^:]*?:?)interface-state-ref$")

def fixup_stmt(stmt):
    # Replace referenced to inteface-state-ref with inteface-ref
    if stmt.keyword == 'type':
        m = if_state_ref_pattern.match(stmt.arg)
        if m:
            stmt.arg = m.group(1) + "interface-ref"
            
    for s in stmt.substmts:
        fixup_stmt(s)
    
def convert_stmt(config_stmt, state_stmt):
    # Iterate the state tree
    state_substmts = grammar.sort_canonical(state_stmt.keyword, state_stmt.substmts)
    config_substmts = grammar.sort_canonical(config_stmt.keyword, config_stmt.substmts)
    for s in state_substmts:
        matching_cfg_stmts = [c for c in config_substmts if is_matching_stmt(c, s)]
        if any(matching_cfg_stmts):
            cfg_stmt = matching_cfg_stmts[0]
            
            if (s.keyword in ['description', 'presence']):
                if s.arg != cfg_stmt.arg:
                    # Merge description strings.
                    cfg_stmt.arg = cfg_stmt.arg + "\n\nFROM STATE TREE (FIX ME):\n" + s.arg
            else:        
                # Don't add this element (should also check type as well).
                convert_stmt(cfg_stmt, s)
        else:
            if (s.keyword != 'config'):
                # Copy the state stmt over to the config
                copied_stmt = s.copy()
                config_stmt.substmts.append(copied_stmt)
                fixup_stmt(copied_stmt)
                if copied_stmt.keyword in {"container", "leaf", "leaf-list", "list", "anyxml", "anydata", "choice"}:
                    add_substmt_canonical(copied_stmt,
                                          Statement(copied_stmt.top, copied_stmt, copied_stmt.pos,
                                                    'config', 'false'))
                
def mark_stmt_deprecated(state_stmt):
    # Iterate the state tree
    def can_have_status(stmt):
        return (stmt.keyword in ['action', 'anydata', 'anyxml', 'augment', 'bits',
                                 'case', 'choice', 'container', 'enum', 'extension',
                                 'feature', 'grouping', 'identity', 'leaf', 'list',
                                 'leaf-list', 'notification', 'rpc', 'typedef', 'uses'])  
    if (can_have_status(state_stmt)):
        status_current = True
        for substmt in state_stmt.substmts:
            if (substmt.keyword == 'status' and substmt.arg != "current"):
                status_current = False
        if (status_current):
            add_substmt_canonical(state_stmt,
                                  Statement(state_stmt.top,
                                            state_stmt,
                                            state_stmt.pos,
                                            'status',
                                            'deprecated'))
    # Recurse down children state statements.
    for substmt in state_stmt.substmts:
        mark_stmt_deprecated(substmt)


# Convert an IETF module, assume "-state" is a top level split.
def convert_module(ctx, m_stmt):
    if ctx.opts.yang_remove_unused_imports and m_stmt.keyword == 'import':
        for p in m_stmt.parent.i_unused_prefixes:
            if m_stmt.parent.i_unused_prefixes[p] == m_stmt:
                return

    if util.is_prefixed(m_stmt.raw_keyword):
        (prefix, identifier) = m_stmt.raw_keyword
        keyword = prefix + ':' + identifier
    else:
        keyword = m_stmt.keyword

    if keyword in ['module', 'submodule']:
        # Don't change the module name, but could update the revision number?
        #module_name = m_stmt.arg
        #m_stmt.arg = module_name + '-2'
        
        # Look for config/state containers to convert.
        if len(m_stmt.substmts) != 0:
            m_substmts = grammar.sort_canonical(m_stmt.keyword, m_stmt.substmts)
            for substmt in m_substmts:
                if substmt.keyword in ['namespace', 'belongs-to']:
                    substmt.arg = substmt.arg + '-2'
                
                # Remove the interface state ref?
                # Or, is this even appropriate.
                if substmt.keyword == 'typedef' and substmt.arg == 'interface-state-ref':
                    m_stmt.substmts.remove(substmt)
                
                # Fix up import references to point to the combined modules.
                #if (substmt.keyword in ['import', 'include']
                #    and substmt.arg.startswith("ietf-")
                #    and substmt.arg not in ["ietf-yang-types","ietf-inet-types"]):
                #    substmt.arg = substmt.arg + "-2"
                
                # Handle top level config/state containers.
                if is_config_container(substmt):
                    for s in m_substmts:
                        if (s.arg == (substmt.arg + "-state") and is_state_container(s)):
                            convert_stmt(substmt, s)
                            
                            # Either remove the m_substmts, or mark it as status deprecated.
                            if IetfModelPlugin.remove_state:
                                m_stmt.substmts.remove(s)
                            else:
                                mark_stmt_deprecated(s)
                
                            
                # Handle top level augmentations of config/state containers.
                if is_state_augmentation(substmt):
                    cfg_augment = [c for c in m_substmts if matches_cfg_augment(c, substmt)] 
                    if cfg_augment:
                        cfg_stmt = cfg_augment[0]
                        convert_stmt(cfg_stmt, substmt)
                        
                        # Either remove the m_substmts, or mark it as status deprecated.
                        if IetfModelPlugin.remove_state:
                            m_stmt.substmts.remove(substmt)
                        else:
                            mark_stmt_deprecated(substmt)
                    else:
                        # If it is just a state augmentation then just rename the augmentation.
                        cfg_arg = matching_cfg_augment(substmt.arg)
                        substmt.arg = cfg_arg           
                            
                # Run the fixup on any groupings (e.g. to fix up type references)
                if substmt.keyword == 'grouping':
                    fixup_stmt(substmt)
        
