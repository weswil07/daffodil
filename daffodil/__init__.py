from parsimonious.grammar import Grammar
from .predicate import DictionaryPredicateDelegate
from .django_hstore import HStoreQueryDelegate



# loosely based on https://github.com/halst/mini/blob/master/mini.py
class Daffodil(object):
    """
    Naming:
        "Data Filtering" -> "DataFil" -> "Daffodil"
                (shortened to)    (sounds like)
        
    
    {} - all
    [] - any
    
    women between 18 and 34:
      {
      gender = "female"
      age > 18
      age < 34
      }
    
    people who are 18 or 21
      [
        age = 18
        age = 21
      ]
      
    men between 18 and 34 and women between 25 and 34
      [
        {
          gender = "female"
          age > 25
          age < 34
        }
        {
          gender = "male"
          age > 18
          age < 34
        }
      ]
    """
    def __init__(self, source):
        self.ast = self.parse("{" + source + "}")

    @property
    def predicate(self):
        if not hasattr(self, "_predicate"):
            self.delegate = DictionaryPredicateDelegate()
            self._predicate = self.eval(self.ast)
            self.delegate = None
        return self._predicate

    @property
    def hstore_query(self):
        if not hasattr(self, "_hstore_q"):
            self.delegate = HStoreQueryDelegate()
            self._hstore_q = self.eval(self.ast)
            self.delegate = None
        return self._hstore_q

    def parse(self, source):
        grammar_def = '\n'.join(v.__doc__ for k, v in vars(self.__class__).items()
                      if '__' not in k and hasattr(v, '__doc__') and v.__doc__)
        self.grammar = Grammar(grammar_def)
        return self.grammar['program'].parse(source)

    def eval(self, source):
        node = self.parse(source) if isinstance(source, basestring) else source
        method = getattr(self, node.expr_name, lambda node, children: children)
        return method(node, [self.eval(n) for n in node])

    def program(self, node, children):
        'program = expr'
        return children[0]
    
    def all(self, node, children):
        'all = "{" expr* "}"'
        child_expressions = children[1]
        return self.delegate.mk_all(child_expressions)
        
    def any(self, node, children):
        'any = "[" expr* "]"'
        child_expressions = children[1]
        return self.delegate.mk_any(child_expressions)
        
    def expr(self, node, children):
        '''expr = _ (all / any / condition) _ ~"[\\n\,]?" _'''
        return children[1][0]
    
    def condition(self, node, children):
        'condition = _ key _ test _ value _'
        _, key, _, test, _, val, _ = children
        return self.delegate.mk_cmp(key, val, test)

    def key(self, node, children):
        'key = string / bare_key'
        return children[0]
        
    def bare_key(self, node, children):
        'bare_key = ~"[a-zA-Z0-9_-]+"'
        return node.text
        
    def test(self, node, children):
        'test = "!=" / "?=" / "<=" / ">=" / "=" / "<" / ">"'
        return self.delegate.mk_test(node.text)
    
    def value(self, node, children):
        'value = number / string / boolean'
        return children[0]
        
    def string(self, node, children):
        'string = doubleString / singleString'
        return unicode(node.text[1:-1])
        
    def doubleString(self, node, children):
        '''
        doubleString = ~'"([^"]|(\"))*?"'
        '''
        return node.text
    
    def singleString(self, node, children):
        '''
        singleString = ~"'([^']|(\'))*?'"
        '''
        return node.text    

    def number(self, node, children):
        'number =  float / integer'
        return children[0]
    
    def integer(self, node, children):
        'integer = ~"[0-9]+"'
        return int(node.text)
    
    def boolean(self, node, children):
        '''
        boolean = ~"true|false"i
        '''
        return node.text.lower() == "true"
    
    def float(self, node, children):
        'float = ~"[0-9]*\.[0-9]+"'
        return float(node.text)

    def _(self, node, children):
        '_ = ~"[\\n\s]*"m'
        
    def __call__(self, iterable):
        return filter(self.predicate, iterable)
