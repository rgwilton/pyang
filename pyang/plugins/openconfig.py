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


def i_to_o_list_keys(stmt, new_list):
    """Return a new list statement in OC format."""
    assert stmt.keyword == "list", "Expected list statement"

    # For each child of the list:
    #  - create a new top-level leafref for any keys mapping to the
    #    respective item in the new config container.
    for child in stmt.i_children:
        if (child.i_config and
            hasattr(child, "i_is_key") and
            child.i_is_key):
            # Add a leaf-ref under the list.
            new_child = statements.Statement(stmt.top, new_list, stmt.pos,
                                             "leaf", child.arg)
            new_child.i_config = True
            new_child.i_module = stmt.i_module
            new_list.substmts.append(new_child)
            new_list.i_children.append(new_child)
            new_list.i_key.append(new_child)

            new_child_type = statements.Statement(stmt.top, new_child,
                                                  stmt.pos, "type",
                                                  "leafref")
            new_child_type.i_config = True
            new_child_type.i_module = stmt.i_module
            new_child_type.i_children = []
            new_child.substmts.append(new_child_type)

            new_child_desc = statements.Statement(
                stmt.top, new_child, stmt.pos, "description",
                "Structural leafref to equivalent leaf in ./config container")
            new_child.substmts.append(new_child_desc)

            new_child_type_path = statements.Statement(
                stmt.top, new_child_type, stmt.pos, "path",
                "../config/{}".format(new_child.arg))
            new_child_type_path.i_config = True
            new_child_type_path.i_module = stmt.i_module
            new_child_type.substmts.append(new_child_type_path)


def fix_leafref(stmt):
    """Fixup leafref statements because the leaf is moved down one container level."""
    type_stmt = stmt.search_one("type")
    if type_stmt is not None and type_stmt.arg == "leafref":
        path_stmt = type_stmt.search_one("path")
        if path_stmt is not None and path_stmt.arg.startswith("../"):
            path_stmt.arg = "../" + path_stmt.arg

def create_config_and_state_containers(parent):
    config = statements.Statement(parent.top, parent, parent.pos,
                                  "container", "config")
    config.i_config = True
#    config.i_module = parent.i_module
#    config.i_children = []
    
    config_desc = statements.Statement(parent.top, config, parent.pos,
                                      "description", "Contains intended configuration")
    config.substmts.append(config_desc)
    config.inserted = False


    state = statements.Statement(parent.top, parent, parent.pos,
                                 "container", "state")
    state.i_config = False
#    state.i_module = parent.i_module
#    state.i_children = []

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

def i_to_o_container(stmt):
    """Return a new container/list/etc. in OC format."""
    
    # Make a new statement.
    new_node = stmt.copy()
    new_node.i_config = True
    new_node.i_children = [c for c in stmt.i_children
                           if c.keyword not in
                               statements.data_definition_keywords]
    new_node.i_key = []
    new_node.substmts = [c for c in stmt.substmts
                         if c.keyword not in 
                             statements.data_definition_keywords]

    # Create a new config container under the container.
    # Create a new state container under the container with config false.
    # For each child of the container:
    #  - put each config child into both new containers
    #  - put each non-config child into the state container
    (config, state) = create_config_and_state_containers(new_node)

    if stmt.keyword == "list":
        # Add new leaf-ref keys
        i_to_o_list_keys(stmt, new_node)

    if (stmt.keyword == "container" and
            stmt.search_one("presence") is not None):
        # Add an "enabled" leaf of type bool to each new container.
        enabled = create_enabled_leaf(config)
        config.substmts.append(enabled)
        config.i_children.append(enabled)

        enabled_s = enabled.copy(parent=state)
        enabled_s.i_config = False
        state.substmts.append(enabled)
        state.i_children.append(enabled)

    for child in stmt.i_children:
        # N.B. This will result in containers as substatements of the
        # "state" container (e.g. statistics in the interface model).
        if child.i_config:
            if child.keyword in ("list", "container", "augment"):
                new_child = i_to_o_container(child)
                new_node.substmts.append(new_child)
                new_node.i_children.append(new_child)
            else:
                # Fix up leafref paths to account for the extra container level.
                fix_leafref(child)
                
                child_copy = child.copy()
                child_copy.i_config = False

                config.substmts.append(child)
                config.i_children.append(child)
                
                # Preserve order.
                if not config.inserted:
                    new_node.substmts.append(config)
                    new_node.i_children.append(config)
                    config.inserted = True

                state.substmts.append(child_copy)
                state.i_children.append(child_copy)
                if not state.inserted:
                    new_node.substmts.append(state)
                    new_node.i_children.append(state)
                    state.inserted = True
        else:
            # Remove the config false statement.
            config_stmt = child.search_one("config")
            if config_stmt is not None:
                child.substmts.remove(config_stmt)
            # Append the child to the new state container.
            state.substmts.append(child)
            state.i_children.append(child)
        
    return new_node

def i_to_o_list_keys_new(stmt):
    """Return a new list statement in OC format."""
    assert stmt.keyword == "list", "Expected list statement"

    index = 0
    # For each child of the list:
    #  - create a new top-level leafref for any keys mapping to the
    #    respective item in the new config container.
    for child in stmt.i_children:
        if (child.i_config and
            hasattr(child, "i_is_key") and
            child.i_is_key):
            
            # Prepend a leaf-ref under the list.
            key_leafref = statements.Statement(stmt.top, stmt, stmt.pos,
                                             "leaf", child.arg)
            key_leafref.i_config = True
            key_leafref.i_module = stmt.i_module
            stmt.substmts.insert(index, key_leafref)
            stmt.i_children.insert(index, key_leafref)
            stmt.i_key.insert(index, key_leafref)

            new_child_type = statements.Statement(stmt.top, key_leafref,
                                                  stmt.pos, "type",
                                                  "leafref")
            new_child_type.i_config = True
            new_child_type.i_module = stmt.i_module
            new_child_type.i_children = []
            key_leafref.substmts.append(new_child_type)

            new_child_desc = statements.Statement(
                stmt.top, key_leafref, stmt.pos, "description",
                "Structural leafref to equivalent leaf in ./config container")
            key_leafref.substmts.append(new_child_desc)

            new_child_type_path = statements.Statement(
                stmt.top, new_child_type, stmt.pos, "path",
                "../config/{}".format(key_leafref.arg))
            new_child_type_path.i_config = True
            new_child_type_path.i_module = stmt.i_module
            new_child_type.substmts.append(new_child_type_path)
            
            index += 1

def cfg_stmt_move(stmt, parent, config, state):
    #parent = stmt.parent
    
    # Fix up leafref paths to account for the extra container level.
    fix_leafref(stmt)
    
    s_index = parent.substmts.index(stmt)
#    i_index = parent.i_children.index(stmt)
    
    if not config.inserted:
        parent.substmts.insert(s_index, config)
#        parent.i_children.insert(i_index, config)
        config.inserted = True    
    
    if not state.inserted:
        parent.substmts.insert(s_index + 1, state)
#        parent.i_children.insert(i_index + 1, state)
        state.inserted = True
        
    # Remove the existing stmt from the parent.
    parent.substmts.remove(stmt)
#    parent.i_children.remove(stmt)
    
    child_copy = stmt.copy()
    child_copy.i_config = False

    config.substmts.append(stmt)
#    config.i_children.append(stmt)
    
    state.substmts.append(child_copy)
#    state.i_children.append(child_copy)
    
def state_stmt_move(stmt, parent, config, state):
    #parent = stmt.parent
    
    # Fix up leafref paths to account for the extra container level.
    fix_leafref(stmt)
    
    s_index = parent.substmts.index(stmt)
    del parent.substmts[s_index]
#    i_index = parent.i_children.index(stmt)
    
    # Remove the existing stmt from the parent.
    #parent.substmts.remove(stmt)
#    parent.i_children.remove(stmt)
    
    if not config.inserted:
        parent.substmts.insert(s_index, config)
#        parent.i_children.insert(i_index, config)
        config.inserted = True    
    
    if not state.inserted:
        parent.substmts.insert(s_index + 1, state)
#        parent.i_children.insert(i_index + 1, state)
        state.inserted = True
    
    # Remove the config false statement.
    config_stmt = stmt.search_one("config")
    if config_stmt is not None:
        stmt.substmts.remove(config_stmt)
    # Append the child to the new state container.
    state.substmts.append(stmt)
#    state.i_children.append(stmt)

# Pass in the stmt to process, the parent, and parent config/state containers to add elements to.
def i_to_o_stmt(stmt, parent, config, state):
    """Convert the current stmt to OC format."""

    # Create a new config container under the container.
    # Create a new state container under the container with config false.
    # For each child of the container:
    #  - put each config child into both new containers
    #  - put each non-config child into the state container
    if stmt.keyword in ("list", "container"):
        # Container have config/state at a lower level.
        # Then statements are only added if they are used.
        (config, state) = create_config_and_state_containers(stmt)

    if stmt.keyword == "list":
        # Add new leaf-ref keys
        i_to_o_list_keys_new(stmt)

    if (stmt.keyword == "container" and
            stmt.search_one("presence") is not None):
        # Add an "enabled" leaf of type bool to each new container.
        enabled = create_enabled_leaf(config)
        config.substmts.append(enabled)
#        config.i_children.append(enabled)

        enabled_s = enabled.copy(parent=state)
        enabled_s.i_config = False
        state.substmts.append(enabled)
#        state.i_children.append(enabled)

    #for child in stmt.i_children:
        # N.B. This will result in containers as substatements of the
        # "state" container (e.g. statistics in the interface model).
    if hasattr(stmt, 'i_config'):
        if stmt.i_config:
            if stmt.keyword in ("list", "container", "augment"):
                for s in stmt.substmts:
                    i_to_o_stmt(s, stmt, config, state)
            else:
                #cfg_stmt_move(stmt, parent, config, state)
                pass
        else:
            # Remove the config false statement.
            #state_stmt_move(stmt, parent, config, state)
            pass

def ietf_to_oc_2(module):
    """Return a new module tree in OpenConfig format."""
    module.arg += "-oc"
    module.i_modulename = module.arg

    # Iterate through the tree.
    (config, state) = create_config_and_state_containers(module)
    for stmt in module.substmts:
        if stmt.keyword in ("container", "list", "augment"):
            i_to_o_stmt(stmt, module, config, state)

    return module

def ietf_to_oc(module):
    """Return a new module tree in OpenConfig format."""
    module.arg += "-oc"
    module.i_modulename = module.arg

    if any(c.keyword == "augment" for c in module.substmts):
        # Find the IETF interfaces import and replace it with
        # Openconfig interfaces import.
        imp = statements.Statement(module.top, module, module.pos,
                                   "import", "openconfig-interfaces")
        imp.i_module = module
        pref = statements.Statement(module.top, module, module.pos,
                                    "prefix", "oc-if")
        pref.i_module = module
        imp.substmts = [pref]

        for i, s in enumerate(module.substmts):
            if s.keyword == "import" and "ietf-interfaces" in s.arg:
                module.substmts[i] = imp
                break

    # Iterate through the tree.
    # Looks for any list with config.
    for child in module.substmts:
        if child.keyword in ("container", "list", "augment"):
            new_node = i_to_o_container(child)
            if child.keyword == "augment":
                new_node.arg = "/oc-if:interfaces/oc-if:interface"
            try:
                index = module.i_children.index(child)
                module.i_children[index] = new_node
            except ValueError:
                pass
            index = module.substmts.index(child)
            module.substmts[index] = new_node

    return module

def pyang_plugin_init():
    plugin.register_plugin(OpenConfigPlugin())


class OpenConfigPlugin(plugin.PyangPlugin):
    def setup_fmt(self, ctx):
        ctx.implicit_errors = True

    def add_opts(self, optparser):
        optparser.add_option("--ietf-to-oc", dest="ietf_to_oc",
                             action="store_true",
                             help="Convert IETF module format to OpenConfig")

    def post_validate_ctx(self, ctx, modules):
        # Run the plugin here.
        if ctx.opts.ietf_to_oc:
            modules = [ietf_to_oc_2(m) for m in modules]
