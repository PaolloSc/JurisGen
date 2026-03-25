import json  
from jusbrasil_search import JusBrasilSearch  
def test():  
    searcher = JusBrasilSearch()  
    print("Iniciando busca no JusBrasil...")  
    resultados = searcher.buscar_jurisprudencia("horas extras", "TST", 3)  
    print(json.dumps(resultados, indent=2, ensure_ascii=False))  
if __name__ == '__main__': test() 
