from serpapi import GoogleSearch


def search_recipes_serpapi(query):
  print ("DEBUG serpapi triggered with query:", query)
  params = {
    "q": query,
    "hl": "en",
    "num": 30,  # explicitly specifying the number 100
    "gl": "us",
    "api_key": "5dfc2b51a4c7d1866b5aca18c49f902cec425ca083affe953bfa5b0c9767de07"
  }

  search = GoogleSearch(params)
  
  #recipes_results = results["recipes_results"]
  results = search.get_dict()

  # Extract just the recipes_results array
  #recipes_results = results.get('recipes_results', [])

  
  # Save results to a text file
  with open('recipes_results.txt', 'w', encoding='utf-8') as file:
    file.write(str(results))
  
  return  results
if __name__ == "__main__":
  returned = search_recipes_serpapi('meat stuffed cabbage recipes "ginger" ')
  print (returned)


  
    # Run the following manually in the shell as needed
    # query = input("Enter your search query for recipes: ")
    # results = search_recipes_serpapi(query)
    # for i, recipe in enumerate(results, start=1):
    #     print(f"{i}. {recipe['title']}: {recipe['link']}")