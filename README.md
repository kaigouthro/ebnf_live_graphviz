Uses Ace editor ( set to coffee for highlighting ).


caveat :

not this:
```
rulenamee 
  ::= blahblah
  | blahtwo
  | blahthree
```

fix it to this:

```
rulenamee ::= blahblah | blahtwo | blahthree
```  

rules each on one line (sorry, lazy)

cmd line:

```streamlit run ebnf_visualizer.py```
