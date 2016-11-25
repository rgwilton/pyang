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


def i_to_o_list(stmt):
    """Return a new list statement in OC format."""
    assert stmt.keyword == "list", "Expected list statement"

    # Make a new list statement.
    new_list = statements.Statement(stmt.top, stmt.parent, stmt.pos,
                                    "list", stmt.arg)
    new_list.i_config = True
    new_list.i_children = []

    # Create a new config container under the list.
    # Create a new state container under the list with config set to false.
    # For each child of the list:
    #  - put each config child into both new containers
    #  - put each non-config child into the state container
    #  - create a new top-level leafref for any keys mapping to the
    #    respective item in the new config container.

    config = statements.Statement(stmt.top, new_list, stmt.pos,
                                  "container", "config")
    config.i_config = True
    config.i_children = []

    state = statements.Statement(stmt.top, new_list, stmt.pos,
                                 "container", "state")
    state.i_config = False
    state.i_children = []
    state_config = statements.Statement(stmt.top, state, stmt.pos,
                                        "config", "false")
    state.substmts.append(state_config)

    for child in stmt.i_children:
        if child.i_config:
            child_copy = child.copy()
            child_copy.i_config = False

            config.substmts.append(child)
            config.i_children.append(child)

            state.substmts.append(child_copy)
            state.i_children.append(child_copy)

            if child.get("i_is_key", False):
                # Add a leaf-ref under the list.
                new_child = statements.Statement(stmt.top, new_list, stmt.pos,
                                                 "leaf", child.arg)
                new_child.i_config = True
                new_list.substmts.append(new_child)
                new_list.i_children.append(new_child)

                new_child_type = statements.Statement(stmt.top, new_child,
                                                      stmt.pos, "type",
                                                      "leafref")
                new_child_type.i_config = True
                new_child_type.i_children = []
                new_child.substmts.append(new_child_type)

                new_child_type_path = statements.Statement(
                    stmt.top, new_child_type, stmt.pos, "path",
                    "../config/{}".format(new_child.arg))
                new_child_type_path.i_config = True
                new_child_type.substmts.append(new_child_type_path)
        else:
            state.substmts.add(child)
            state.i_children.append(child)

    return new_list


def ietf_to_oc(module):
    """Return a new module tree in OpenConfig format."""
    # Duplicate the top module node.
    old_module = copy.copy(module)

    # Iterate through the tree.
    # Looks for any list with config.
    def walk(stmt):
        for child in stmt.i_children:
            if child.keyword == "list":
                new_list = i_to_o_list(child)
                try:
                    index = stmt.substmts.index(child)
                    stmt.substmts[index] = new_list
                except IndexError:
                    pass
                index = stmt.i_children.index(child)
                stmt.i_children[index] = new_list

    walk(module)


def oc_to_ietf(module):
    """Return a new module tree in IETF format."""
    # Duplicate the top module node.
    old_module = copy.copy(module)

    #



def pyang_plugin_init():
    plugin.register_plugin(OpenConfigPlugin())


class OpenConfigPlugin(plugin.PyangPlugin):
    def setup_fmt(self, ctx):
        ctx.implicit_errors = True

    def add_opts(self, optparser):
        optparser.add_option("--oc-to-ietf", dest="oc_to_ietf",
                             action="store_true",
                             help="Convert OpenConfig model format to IETF")
        optparser.add_option("--itef-to-oc", dest="ietf_to_oc",
                             action="store_true",
                             help="Convert OpenConfig model format to IETF")

    def post_validate(self, ctx, modules):
        # Run the plugin here.
        if ctx.args.ietf_to_oc:
            ietf_to_oc(modules[0])
