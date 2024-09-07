import re
import sys
import subprocess
import tempfile

# get graph viz
# subprocess.check_call([sys.executable, "-m", "pip", "install", "graphviz","streamlit_ace", "streamlit-agraph"])

import graphviz as graphviz
import streamlit as st
from streamlit_ace import st_ace
from streamlit_agraph import Edge, Node, agraph
from streamlit_agraph.config import Config, ConfigBuilder


examplegrammar = """
Grammar  ::= Production*
Production
         ::= NCName '::=' ( Choice | Link )
NCName   ::= Name - (Char* ':' Char*)
Choice   ::= SequenceOrDifference ( '|' SequenceOrDifference )*
SequenceOrDifference
         ::= (Item ( '-' Item | Item* ))?
Item     ::= Primary ( '?' | '*' | '+' )*
Primary  ::= NCName | StringLiteral | CharCode | CharClass | '(' Choice ')'
StringLiteral
         ::= '"' [^"]* '"' | "'" [^']* "'"
          /* ws: explicit */
CharCode ::= '#x' [0-9a-fA-F]+
          /* ws: explicit */
CharClass
         ::= '[' '^'? ( Char | CharCode | CharRange | CharCodeRange )+ ']'
          /* ws: explicit */
Char     ::= [#x9#xA#xD#x20-#xD7FF#xE000-#xFFFD#x10000-#x10FFFF]
CharRange
         ::= Char '-' ( Char - ']' )
          /* ws: explicit */
CharCodeRange
         ::= CharCode '-' CharCode
          /* ws: explicit */
Link     ::= '[' URL ']'
URL      ::= [^#x5D:/?#]+ '://' [^#x5D#]+ ('#' NCName)?
          /* ws: explicit */
Whitespace
         ::= S | Comment
S        ::= #x9 | #xA | #xD | #x20
Comment  ::= '/*' ( [^*] | '*'+ [^*/] )* '*'* '*/'
          /* ws: explicit */
"""


# Grammar Guide
class Grammar:
    def __init__(self):
        self.grammar = ""
        self.rules = {}
        self.terminals = set()
        self.tokens = {}
        self.graph = graphviz.Digraph()
        self.json = False
        self.specific = False
        self.graphic = False
        self.showMD = False
        self.ran = False
        self.main = st.container
        self.nodes = []
        self.edges = []

    def parse(self):
        side = st.sidebar
        with side:
            st.markdown("# Grammar Guide")
            st.markdown("[converter here](https://www.bottlecaps.de/convert/)")
            st.markdown("```https://www.bottlecaps.de/convert/```")
            auto = st.checkbox(
                key="autogen",
                label="Auto-generate grammar live for graphviz",
                value=False,
            )
            show = (
                "graphviz"
                if auto
                else st.selectbox(
                    "Show Grammar as..", ["markdown", "json", "specific", "graphviz"]
                )
            )
            Font = st.slider("Font size", 12, 16, 20, key="font")
        with self.main():
            self.grammar = st_ace(
                value=examplegrammar,
                auto_update=auto,
                show_gutter=False,
                font_size=Font,
                language="coffee",
                theme="monokai",
            )
        # if change, set ran to no
        if self.grammar:
            self.ran = False

        self.graphic = show == "graphviz"
        self.json = show == "json"
        self.specific = show == "specific"
        self.showMD = show == "markdown"
        if auto:
            self.graphic = True

        if not self.ran and self.grammar:
            self.ran = True
            self.parse_grammar()
            if self.graphic:
                self.build_graph()

    def parse_grammar(self):
        grammar = self.grammar

        # find all rules
        for rule_match in re.findall(
            r"^\s*([A-Za-z0-9_]+)\s*::=\s*(.+)$", grammar, re.MULTILINE
        ):
            rule_name, rule_definition = rule_match
            self.rules[rule_name] = {"called_by": [], "tokens": []}

            # Parse the rule definition
            tokens = re.findall(
                r"([A-Za-z0-9_]+|\[[^\]]+\]|'[^']+'|\"[^\"]+\")", rule_definition
            )

            for i, token in enumerate(tokens):
                # Extract and convert #x... characters
                token = re.sub(
                    r"#x([0-9a-fA-F]+)", lambda m: chr(int(m.group(1), 16)), token
                )

                modifier = self.get_modifier(token)

                # Handle [^...] for "anything except"
                if re.match(r"\[[^\]]+\]", token):
                    token_type = "anything except"
                    excluded_chars = token[1:-1]  # Extract characters between brackets
                    # If '^' is present, it means "anything except these characters"
                    if excluded_chars.startswith("^"):
                        excluded_chars = excluded_chars[1:]
                        token = f"anything except: {excluded_chars}"  # Display excluded characters
                    else:
                        token = f"only these characters: {excluded_chars}"  # Display included characters

                    self.rules[rule_name]["tokens"].append(
                        {"type": token_type, "value": token, "modifier": modifier}
                    )
                    continue

                token_type = "rule" if token in self.rules else "terminal"
                if token_type == "terminal":
                    self.terminals.add(token)

                self.rules[rule_name]["tokens"].append(
                    {"type": token_type, "value": token, "modifier": modifier}
                )

        for rule_name, rule_data in self.rules.items():
            for token_data in rule_data["tokens"]:
                if token_data["type"] == "rule":
                    self.rules[token_data["value"]]["called_by"].append(rule_name)

        with self.main():
            if self.json:
                st.write(self.rules)
            if self.specific:
                st.write(self.rules)

    @staticmethod
    def get_modifier(rule: str):
        if rule.endswith("?"):
            return "optional"
        elif rule.endswith("*"):
            return "zero or more"
        elif rule.endswith("+"):
            return "one or more"
        else:
            return "none"

    def build_graph(self):
        if not self.graphic:
            return
        self.showGV = st.sidebar.checkbox("Show Graphviz", value=False)
        self.color1 = st.sidebar.color_picker("Color 1", "#aaf", key="color1")
        self.color2 = st.sidebar.color_picker("Color 2", "#ffc", key="color2")
        self.color3 = st.sidebar.color_picker("Color 3", "#cfc", key="color3")
        self.color4 = st.sidebar.color_picker("Color 4", "#cff", key="color4")
        for rule_name, rule_data in self.rules.items():
            if not any(node.id == rule_name for node in self.nodes):
                self.nodes.append(
                    Node(id=rule_name, label=rule_name, color=self.color1, shape="box")
                )
                self.graph.node(rule_name, shape="box")

            for token_data in rule_data["tokens"]:
                token_name = token_data["value"]
                if token_data["type"] == "terminal":
                    if not any(node.id == token_name for node in self.nodes):
                        self.nodes.append(
                            Node(
                                id=token_name,
                                label=token_name,
                                color=self.color2,
                                shape="ellipse",
                            )
                        )
                        self.graph.node(token_name, shape="ellipse")
                    self.edges.append(
                        Edge(source=token_name, target=rule_name, color=self.color4)
                    )
                    self.graph.edge(token_name, rule_name, color=self.color4)
                else:
                    self.edges.append(
                        Edge(source=token_name, target=rule_name, color=self.color3)
                    )
                    self.graph.edge(token_name, rule_name, color=self.color3)

        for rule_name, rule_data in self.rules.items():
            for called_by in rule_data["called_by"]:
                self.edges.append(
                    Edge(source=called_by, target=rule_name, color=self.color3)
                )
                self.graph.edge(called_by, rule_name, color=self.color3)

        self.config_builder = ConfigBuilder(self.nodes)
        config = self.config_builder.build()

        agraph(nodes=self.nodes, edges=self.edges, config=config)

        if self.showGV:
            st.graphviz_chart(self.graph.source, use_container_width=True)
            st.code(self.graph.source)


# create the grammar
if __name__ == "__main__":
    Gram = Grammar()
    Gram.parse()
