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

            new_child_type_path = statements.Statement(
                stmt.top, new_child_type, stmt.pos, "path",
                "../config/{}".format(new_child.arg))
            new_child_type_path.i_config = True
            new_child_type_path.i_module = stmt.i_module
            new_child_type.substmts.append(new_child_type_path)


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
    config = statements.Statement(stmt.top, new_node, stmt.pos,
                                  "container", "config")
    config.i_config = True
    config.i_module = stmt.i_module
    config.i_children = []

    state = statements.Statement(stmt.top, new_node, stmt.pos,
                                 "container", "state")
    state.i_config = False
    state.i_module = stmt.i_module
    state.i_children = []

    state_config = statements.Statement(stmt.top, state, stmt.pos,
                                        "config", "false")
    state.substmts.append(state_config)

    if stmt.keyword == "list":
        # Add new leaf-ref keys
        i_to_o_list_keys(stmt, new_node)

    for child in stmt.i_children:
        if child.i_config:
            if child.keyword in ("list", "container"):
                new_child = i_to_o_container(child)
                new_node.substmts.append(new_child)
                new_node.i_children.append(new_child)
            else:
                child_copy = child.copy()
                child_copy.i_config = False

                config.substmts.append(child)
                config.i_children.append(child)

                state.substmts.append(child_copy)
                state.i_children.append(child_copy)
        else:
            state.substmts.append(child)
            state.i_children.append(child)

    if len(config.i_children) > 0:
        new_node.substmts.append(config)
        new_node.i_children.append(config)
    if len(state.i_children) > 0:
        new_node.substmts.append(state)
        new_node.i_children.append(state)

    return new_node


def ietf_to_oc(module):
    """Return a new module tree in OpenConfig format."""
    # Duplicate the top module node.
    old_module = copy.copy(module)

    # Iterate through the tree.
    # Looks for any list with config.
    for child in module.i_children:
        if child.keyword in ("container", "list"):
            new_node = i_to_o_container(child)
            try:
                index = module.substmts.index(child)
                module.substmts[index] = new_node
            except IndexError:
                pass
            index = module.i_children.index(child)
            module.i_children[index] = new_node

    return module


def oc_to_ietf(module):
    """Return a new module tree in IETF format."""
    # Duplicate the top module node.
    old_module = copy.copy(module)


def pyang_plugin_init():
    plugin.register_plugin(OpenConfigPlugin())


class OpenConfigPlugin(plugin.PyangPlugin):
    def setup_fmt(self, ctx):
        ctx.implicit_errors = True

    def add_opts(self, optparser):
        optparser.add_option("--oc-to-ietf", dest="oc_to_ietf",
                             action="store_true",
                             help="Convert OpenConfig model format to IETF")
        optparser.add_option("--ietf-to-oc", dest="ietf_to_oc",
                             action="store_true",
                             help="Convert IETF module format to OpenConfig")

    def post_validate_ctx(self, ctx, modules):
        # Run the plugin here.
        if ctx.opts.ietf_to_oc:
            modules = [ietf_to_oc(m) for m in modules]
