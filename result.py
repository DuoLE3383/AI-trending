def analyze_entries(entries):
  """
  Analyzes a list of entries to count the occurrences of each result.

  Args:
    entries: A list of dictionaries, where each dictionary represents an entry
             and has a 'result' key.

  Returns:
    A dictionary containing the count of each result.
  """
  result_counts = {}
  if not entries:
    return {"error": "No entries provided"}

  for entry in entries:
    if 'result' in entry:
      result = entry['result']
      if result in result_counts:
        result_counts[result] += 1
      else:
        result_counts[result] = 1
  return result_counts

# --- Example Usage ---

# Example list of entries
example_entries = [
    {'entry_id': 1, 'data': '...', 'result': 'win'},
    {'entry_id': 2, 'data': '...', 'result': 'loss'},
    {'entry_id': 3, 'data': '...', 'result': 'win'},
    {'entry_id': 4, 'data': '...', 'result': 'draw'},
    {'entry_id': 5, 'data': '...', 'result': 'win'},
    {'entry_id': 6, 'data': '...', 'result': 'loss'},
]

# Analyze the example entries
analysis = analyze_entries(example_entries)

# Print the results
print(f"Total number of entries: {len(example_entries)}")
print("Result breakdown:")
for result, count in analysis.items():
  print(f"- {result}: {count}")

