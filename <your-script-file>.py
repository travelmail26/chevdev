import json
# ...existing code...

# Assuming `final_result` is the variable holding the final data
output_file = "reddit_output.json"
with open(output_file, "w") as f:
    json.dump(final_result, f, indent=4)

print(f"Results saved to {output_file}")
# ...existing code...
