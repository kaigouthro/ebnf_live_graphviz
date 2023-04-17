import json
import re

import graphviz
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
        self.terminals = {}
        self.tokens = {}
        self.graph = None
        self.json = False
        self.specific = False
        self.graphic = False
        self.showMD = False
        self.ran = False
        self.main = st.container
        self.color1 = st.sidebar.color_picker("Color 1", "#aaf", key="color1")
        self.color2 = st.sidebar.color_picker("Color 2", "#dc0", key="color2")
        self.size1 = st.sidebar.slider("Size 1", 10, 100, 20, key="size1")
        self.size2 = st.sidebar.slider("Size 2", 10, 100, 10, key="size2")
        self.nodes = []
        self.edges = []
        self.parse()

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

        grammar = self.grammar

        # find all rules
        base_rules = re.findall(r"\n([A-Za-z0-9_]+)[\n\s]*::=", grammar)

        while not self.ran:
            self.ran = True

            for base_rule in base_rules:
                self.rules[base_rule] = {"tokens": None, "called_by": []}
                self.rules[base_rule]["tokens"] = {}
                self.terminals[base_rule] = {"terminals": None}
                self.terminals[base_rule]["terminals"] = []

                # find the tokens grouped by tpe if rule or terminal or regex match
                if self.showMD:
                    with self.main():
                        st.markdown("# ```" + base_rule + " ::=``` ")

                # find the items in each rule
                tokens = re.findall(
                    r"\n" + base_rule + r"[\n\s]*::=(\n*\s*[^\n]+\n)+?(?<!\n\w)",
                    grammar,
                )
                for token in tokens:
                    if self.showMD:
                        with self.main():
                            st.markdown("``` " + token + " ```")

                    # for each rule, find the terminals
                    rules = re.findall(
                        r"(([A-Za-z_]+[?*+]?)|(\[.+\\])|(\'[^\']+\'[?*+]))",
                        token,
                    )
                    i = 1
                    self.rules[base_rule]["name"] = base_rule
                    for rule in rules:
                        [fillrule, tokentype] = (
                            [rule[1], "rule"]
                            if rule[1] != ""
                            else [rule[2], "terminal"]
                            if rule[2] != ""
                            else [rule[3], "terminal"]
                        )

                        self.rules[base_rule]["tokens"][i] = {
                            "type": tokentype,
                            "value": fillrule,
                            "modifier": self.get_modifier(fillrule),
                        }
                        i += 1
                        fillrule = (
                            fillrule[0:-1]
                            if fillrule.endswith(("?", "+", "*"))
                            else fillrule
                        )
                        if self.showMD:
                            with self.main():
                                st.markdown(
                                    "- #### " + tokentype + ": ```" + fillrule + "```"
                                )
                        if fillrule not in self.terminals[base_rule]["terminals"]:
                            self.terminals[base_rule]["terminals"].append(fillrule)

        for base_rule in self.terminals:
            for token in self.terminals[base_rule]["terminals"]:
                token = token[0:-1] if token.endswith(("?", "+", "*")) else token
                if token in self.rules:
                    self.rules[token]["called_by"].append(base_rule)
        with self.main():
            if self.json:
                st.write(self.terminals)
            if self.specific:
                st.write(self.rules)
            if self.graphic:
                self.build_graph()

    @staticmethod
    def get_modifier(rule: str):
        """
        finds if match has a modifier, and returns type..
        TODO: add capability to find parentheses
        """
        if rule.endswith("?"):
            return "1 or none"
        if rule.endswith("*"):
            return "0+"
        if rule.endswith("+"):
            return "1+"
        return "none"

    def build_graph(self):
        # show graph if enabled
        self.graph = graphviz.Digraph(strict=True)
        if self.graphic:
            for rnum, rule in enumerate(self.rules):
                # check self.nodes before adding to avoid duplicates
                if rule not in [node.id for node in self.nodes]:
                    self.nodes.append(
                        Node(
                            id=rule,
                            label=rule,
                            size=self.size1,
                            color=self.color1,
                            shape="box",
                        )
                    )
                    self.graph.node(rule, shape="box")

                for token in self.terminals[rule]["terminals"]:
                    if token not in self.terminals:
                        if token not in [node.id for node in self.nodes]:
                            self.nodes.append(
                                Node(
                                    id=token,
                                    label=token,
                                    size=self.size2,
                                    color=self.color2,
                                )
                            )
                        self.graph.node(token, shape="ellipse")
                    self.edges.append(Edge(source=token, target=rule))
                    self.graph.edge(token, rule)
                    for called in self.rules[rule]["called_by"]:
                        self.edges.append(Edge(source=called, target=rule))
                        self.graph.edge(called, rule)

            self.config_builder = ConfigBuilder(self.nodes)
            config = self.config_builder.build()
            config.width = "100%"

            config.save("config.json")

            config = Config(from_json="config.json")

            agraph(nodes=self.nodes, edges=self.edges, config=config)
            st.graphviz_chart(self.graph, use_container_width=True)
            st.write(self.graph.source)


# create the grammar
if __name__ == "__main__":
    Gram = Grammar()
