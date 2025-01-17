
import os


import logging

print (__file__)

script_dir = os.path.dirname(__file__)

with open(os.path.join(script_dir, 'instructions_base.txt'), 'r') as file:
    content = file.read()
    print(content[:10])
    #system_content_parts.append("=== BASE DEFAULT INSTRUCTIONS ===\n" + content)

#from telegram_bot import setup_bot

# def test_setup_bot():
#     try:
#         # Call the setup_bot function
#         app = setup_bot()
#         print("setup_bot executed successfully.")
#     except Exception as e:
#         # Catch and log any exceptions
#         logging.error(f"Error in setup_bot: {e}")
#         print(f"Error in setup_bot: {e}")

# if __name__ == "__main__":
#     test_setup_bot()


# value = os.environ.get('PRODUCTION_OR_DEVELOPMENT')

# print (value)


#print(fetch_sheet_data_rows('recipe_hummus'))

