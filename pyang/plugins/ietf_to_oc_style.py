# Copyright (c) 2016 by Matthew Green <mgreen89@gmail.com>
#
# Pyang plugin converting between OpenConfig and IETF formats.
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


"""@@@Module docstring"""


import copy
from pyang import plugin
from pyang import statements


def fix_leafref(stmt):
    """Fixup leafref statements because the leaf is moved down one container level."""
    type_stmt = stmt.search_one("type")
    if type_stmt is not None and type_stmt.arg == "leafref":
        path_stmt = type_stmt.search_one("path")
        if path_stmt is not None and path_stmt.arg.startswith("../"):
            path_stmt.arg = "../" + path_stmt.arg

def fix_type(stmt):
    """Fixup type statements to use the module prefix if required"""
    type_stmt = stmt.search_one("type")
    if (type_stmt is not None and
        #type_stmt.arg == "default-policy-type" and
        type_stmt.i_typedef is not None and
        type_stmt.arg.find(":") == -1):
        type_stmt.arg = type_stmt.i_module.i_prefix + ":" + type_stmt.arg


def create_config_and_state_containers(parent):
    config = statements.Statement(parent.top, parent, parent.pos,
                                  "container", "config")
    
    config_desc = statements.Statement(parent.top, config, parent.pos,
                                      "description", "Contains intended configuration")
    config.substmts.append(config_desc)
    config.inserted = False


    state = statements.Statement(parent.top, parent, parent.pos,
                                 "container", "state")

    state_config = statements.Statement(parent.top, state, parent.pos,
                                        "config", "false")
    state.substmts.append(state_config)

    state_desc = statements.Statement(parent.top, state, parent.pos,
                                      "description", "Contains applied configuration and derived state")
    state.substmts.append(state_desc)
    state.inserted = False
    
    return (config, state)  

def create_enabled_leaf(config_parent):
    enabled = statements.Statement(config_parent.top, config_parent, config_parent.pos,
                                   "leaf", "presence")
    enabled.i_children = []
    enabled.i_config = True
    enabled.i_module = config_parent.i_module
    enabled_type = statements.Statement(config_parent.top, enabled, config_parent.pos,
                                        "type", "boolean")
    enabled.substmts.append(enabled_type)
    enabled_desc = statements.Statement(config_parent.top, enabled, config_parent.pos,
                                        "description",
                                        config_parent.search_one("presence").arg)
    enabled.substmts.append(enabled_desc)
    return (enabled)

def i_to_o_list_keys(stmt):
    """Return a new list statement in OC format."""
    assert stmt.keyword == "list", "Expected list statement"
    new_substmts = []

    def attrsearch(tag, attr, lst):
        for x in lst:
            if x.__dict__[attr] == tag:
                return x
        return None

    key_stmt = stmt.search_one('key')
    for x in key_stmt.arg.split():
        if x == '':
            continue
        if x.find(":") == -1:
            name = x
        else:
            [prefix, name] = x.split(':', 1)
             
        #ptr = attrsearch(name, 'arg', stmt.i_children)

        if True:
    # For each child of the list:
    #  - create a new top-level leafref for any keys mapping to the
    #    respective item in the new config container.
    #for child in stmt.i_children:
        #if (hasattr(child, "i_is_key") and child.i_is_key):            
            # Prepend a leaf-ref under the list.
            key_leafref = statements.Statement(stmt.top, stmt, stmt.pos,
                                             "leaf", name)
            key_leafref.i_config = True
            new_substmts.append(key_leafref)
            #stmt.i_key.insert(index, key_leafref)

            new_child_type = statements.Statement(stmt.top, key_leafref,
                                                  stmt.pos, "type",
                                                  "leafref")
            new_child_type.i_config = True
            key_leafref.substmts.append(new_child_type)

            new_child_desc = statements.Statement(
                stmt.top, key_leafref, stmt.pos, "description",
                "Structural leafref to equivalent leaf in ./config container")
            key_leafref.substmts.append(new_child_desc)

            new_child_type_path = statements.Statement(
                stmt.top, new_child_type, stmt.pos, "path",
                "../config/{}".format(key_leafref.arg))
            new_child_type_path.i_config = True
            #new_child_type_path.i_module = stmt.i_module
            new_child_type.substmts.append(new_child_type_path)
            
    return (new_substmts)

def cfg_copy_stmt(stmt, parent, config, state):
    new_substmts = []
    
    # Fix up leafref paths to account for the extra container level.
    fix_leafref(stmt)
    
    if not config.inserted:
        new_substmts.append(config)
        config.inserted = True    
    
    if not state.inserted:
        new_substmts.append(state)
        state.inserted = True
    
    stmt_copy = stmt.copy()
    stmt_copy.i_config = False

    config.substmts.append(stmt)
    state.substmts.append(stmt_copy)
    
    return (new_substmts)
    
    
def state_copy_stmt(stmt, parent, config, state):
    new_substmts = []
    
    # Fix up leafref paths to account for the extra container level.
    fix_leafref(stmt)
    
    stmt_copy = stmt.copy()
    
    if not config.inserted:
        new_substmts.append(config)
        config.inserted = True    
    
    if not state.inserted:
        new_substmts.append(state)
        state.inserted = True
    
    # Remove the config false statement.
    config_stmt = stmt_copy.search_one("config")
    if config_stmt is not None:
        stmt_copy.substmts.remove(config_stmt)

    # Append the child to the new state container.
    state.substmts.append(stmt_copy)
    
    return (new_substmts)

# Pass in the stmt to process, the parent, and parent config/state containers to add elements to.
def expand_state_groupings(stmt, parent):
    """Expand any state tree groupings"""
    new_substmts = []

    def process_substmts(stmt):
        new_stmt = stmt.copy()
        new_substmts = []
        for s in stmt.substmts:
            new_substmts.extend(expand_state_groupings(s, stmt))
        new_stmt.substmts = new_substmts
        return (new_stmt)

    # Create a new config container under the container.
    # Create a new state container under the container with config false.
    # For each child of the container:
    #  - put each config child into both new containers
    #  - put each non-config child into the state container

    if (stmt.keyword == "uses"):
        # Expand out groupings
        for s in stmt.i_grouping.substmts:
            if s.keyword != "description":
                new_substmts.extend(expand_state_groupings(s, parent))
    elif (stmt.keyword == "grouping"):
        #Ignore groupings, since they are expanded.
        pass
    elif stmt.keyword in ("leaf", "leaf-list"):
        fix_type(stmt)
    else:
        new_substmts.append(process_substmts(stmt))
            
    return new_substmts

# Pass in the stmt to process, the parent, and parent config/state containers to add elements to.
def i_to_o_stmt(stmt, parent, config, state, parent_is_config, in_state_tree):
    """Convert the current stmt to OC format."""
    new_substmts = []

    is_config = parent_is_config
    if hasattr(stmt, 'i_config'):
        if stmt.i_config == True or stmt.i_config == False:
            is_config = stmt.i_config

    def process_substmts(stmt, in_state_tree):
        new_stmt = stmt.copy()
        new_substmts = []
        for s in stmt.substmts:
            new_substmts.extend(i_to_o_stmt(s, stmt, config, state, is_config, in_state_tree))
        new_stmt.substmts = new_substmts
        return (new_stmt)

    # Create a new config container under the container.
    # Create a new state container under the container with config false.
    # For each child of the container:
    #  - put each config child into both new containers
    #  - put each non-config child into the state container

    if stmt.keyword == "list": # and is_config == True:
        # Add new leaf-ref keys
        list_key_stmts = i_to_o_list_keys(stmt)

    if (stmt.keyword == "container" and
            stmt.search_one("presence") is not None):
        # Add an "enabled" leaf of type bool to each new container.
        enabled = create_enabled_leaf(config)
        config.substmts.append(enabled)

        enabled_s = enabled.copy(parent=state)
        enabled_s.i_config = False
        state.substmts.append(enabled)

    if (stmt.keyword == "uses"):
        # Expand out groupings
        for s in stmt.i_grouping.substmts:
            if s.keyword != "description":
                new_substmts.extend(i_to_o_stmt(s, parent, config, state, is_config, in_state_tree))
    elif (stmt.keyword == "grouping"):
        #Ignore groupings
        pass
    elif stmt.keyword in ("leaf", "leaf-list"):
        fix_type(stmt)
        if is_config:
            new_substmts.extend(cfg_copy_stmt(stmt, parent, config, state))
        else:
            new_substmts.extend(state_copy_stmt(stmt, parent, config, state))
    elif stmt.keyword in ("list", "container") and is_config:
        # Create new config and state containers for the list.
        (config, state) = create_config_and_state_containers(stmt)
        new_stmt = stmt.copy()
        new_c_substmts = []
        
        if stmt.keyword == "list":
            new_c_substmts.extend(list_key_stmts)
        
        for s in stmt.substmts:
            new_c_substmts.extend(i_to_o_stmt(s, stmt, config, state, is_config, in_state_tree))
        new_stmt.substmts = new_c_substmts
        new_substmts.append(new_stmt)
    elif stmt.keyword in ("list", "container") and not in_state_tree:
        # Remove the config false statement.
        new_stmt = process_substmts(stmt, True)
        new_substmts.extend(state_copy_stmt(new_stmt, parent, config, state))
    else:
        new_substmts.append(process_substmts(stmt, in_state_tree))
            
    return new_substmts

def ietf_to_oc(module):
    """Return a new module tree in OpenConfig format."""
    module.arg += "-oc-style"
    module.i_modulename = module.arg
    new_substmts = []

    # Find all import statements in included modules.
    #for m in module.i_ctx.modules:
    #    if m.i_including_modulename is not None:
    #        for s in m.substmts:
    #            if s.keyword == "import":
    #                new_substmts.append(s)

    # Iterate through the tree.
    (config, state) = create_config_and_state_containers(module)
    for stmt in module.substmts:
        if stmt.keyword == "include":
            for s in stmt.i_module.substmts:
                if s.keyword == "import":
                    print(stmt.i_module.arg + ", " + s.arg + "\n")
                    new_substmts.append(s)
        elif stmt.keyword not in ("grouping"):
            new_substmts.extend(i_to_o_stmt(stmt, module, config, state, True, False))

    module.substmts = new_substmts
    return module

def pyang_plugin_init():
    plugin.register_plugin(OCStylePlugin())


class OCStylePlugin(plugin.PyangPlugin):
    def setup_fmt(self, ctx):
        ctx.implicit_errors = True

    def add_opts(self, optparser):
        optparser.add_option("--ietf-to-oc-style", dest="ietf_to_oc_style",
                             action="store_true",
                             help="Convert IETF module format to OpenConfig style")

    def post_validate_ctx(self, ctx, modules):
        # Run the plugin here.
        if ctx.opts.ietf_to_oc_style:
            modules = [ietf_to_oc(m) for m in modules]
