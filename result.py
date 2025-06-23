# In your file named: results.py

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
      # Add the result to the dictionary and increment its count
      result_counts[result] = result_counts.get(result, 0) + 1
      
  return result_counts

