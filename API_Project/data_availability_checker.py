import openai
import pandas as pd
import os
import tiktoken
import re
import json
from typing import List, Dict, Tuple

# === CONFIGURATION ===
client = openai.OpenAI(api_key="YOUR_API_KEY_HERE")  # Replace with your OpenAI API key
excel_file = "/Users/paschal/Desktop/AER_MHT/AER_2000-2025.xlsx"
readme_folder = "/Users/paschal/Desktop/AER_MHT/downloads/"  # Folder containing README text files
model = "gpt-4o"
temperature = 0.1  # Keep it deterministic
max_tokens = 1000  # Response cap

# === AI PROMPT FOR TABLE DATA AVAILABILITY ===
system_prompt = """You are an assistant helping a researcher identify tables in academic papers that have publicly available datasets suitable for multiple hypothesis testing (MHT) methods."""

user_prompt_template = """
Please analyze the following README text from an academic paper and identify any tables that mention publicly available datasets. Focus specifically on tables that could be suitable for multiple hypothesis testing methods (tables with multiple statistical tests, comparisons, or hypotheses).

For each table you find, look for:
- Table numbers, titles, or descriptions (e.g., "Table 1", "Table A.1", "Appendix Table")
- Explicit mentions that the data for that table is publicly available
- Links to datasets, repositories, or replication files for specific tables
- Instructions for accessing data used in particular tables
- Data repositories (GitHub, Dataverse, ICPSR, Zenodo, OpenICPSR, etc.) linked to specific tables

Do NOT include:
- Tables with data available "upon request" only
- Tables using proprietary or confidential data
- Tables requiring special permissions or agreements
- Simulated data without real-world sources
- Tables mentioned but with no access information

Respond with ONLY a JSON array where each object represents a table with available data:
[
  {
    "table_identifier": "Table 1" or "Table A.2" or similar identifier,
    "table_description": "Brief description of what the table shows",
    "data_available": true/false,
    "data_source": "Description of where the data can be accessed",
    "confidence": "high"/"medium"/"low",
    "evidence": "Brief quote showing the table and data availability connection"
  }
]

If no tables with available data are found, return an empty array: []

README text to analyze:
"""

def read_readme_file(readme_path: str) -> str:
    """Read text from README file"""
    try:
        with open(readme_path, 'r', encoding='utf-8') as file:
            text = file.read()
        return text
    except Exception as e:
        print(f"Error reading README {readme_path}: {str(e)}")
        return ""

def analyze_table_data_availability_with_ai(text: str) -> List[Dict]:
    """
    Use ChatGPT to analyze README text for tables with publicly available data
    Returns list of dictionaries, each containing table information
    """
    # Check token count
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    
    TOKEN_LIMIT = 8000  # Define token limit for the model
    if len(tokens) > TOKEN_LIMIT:
        print(f"Text too long ({len(tokens)} tokens), truncating...")
        # Keep first part of text which usually contains table information
        text = encoding.decode(tokens[:TOKEN_LIMIT])
    
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt_template + text}
            ]
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        try:
            result = json.loads(response_text)
            # Ensure result is a list
            if not isinstance(result, list):
                print(f"Expected list but got: {type(result)}")
                return []
            return result
        except json.JSONDecodeError:
            print(f"Failed to parse JSON response: {response_text}")
            return []
            
    except Exception as e:
        print(f"Error calling OpenAI API: {str(e)}")
        return []

def extract_paper_id_from_filename(filename: str) -> str:
    """Extract paper ID from filename (e.g., AER_3066 from README_AER_3066_...)"""
    match = re.search(r'(AER_\d+)', filename)
    return match.group(1) if match else filename

def find_excel_row_for_paper(df: pd.DataFrame, paper_id: str, readme_filename: str) -> int:
    """Find the corresponding row in Excel for a given paper"""
    
    # Method 1: Try to match by paper ID/number
    paper_number = paper_id.replace('AER_', '')
    for col in df.columns:
        if any(keyword in col.lower() for keyword in ['id', 'number', 'index']):
            mask = df[col].astype(str).str.contains(paper_number, na=False)
            if mask.any():
                return df[mask].index[0]
    
    # Method 2: Try to match by title similarity
    title_from_filename = readme_filename.replace('.pdf', '').replace('README_AER_', '').replace(paper_number + '_', '').replace('_', ' ')
    
    for idx, row in df.iterrows():
        for col in df.columns:
            if 'title' in col.lower():
                if pd.notna(row[col]):
                    excel_title = str(row[col]).lower()
                    filename_words = title_from_filename.lower().split()
                    # Check if at least 3 significant words match
                    significant_words = [w for w in filename_words if len(w) > 3][:5]
                    matches = sum(1 for word in significant_words if word in excel_title)
                    if matches >= 3:
                        return idx
    
    return None

def main():
    print("=== AER Table Data Availability Checker ===")
    print("This script uses AI to analyze README files for tables with publicly available datasets suitable for MHT methods.\n")
    
    # Load the Excel file
    print("Loading Excel file...")
    try:
        df = pd.read_excel(excel_file)
        print(f"Loaded {len(df)} records from Excel file")
    except Exception as e:
        print(f"Error loading Excel file: {str(e)}")
        return
    
    # Initialize new columns if they don't exist
    new_columns = ['Tables_with_data', 'Table_count', 'Table_details']
    for col in new_columns:
        if col not in df.columns:
            if col == 'Table_count':
                df[col] = 0
            else:
                df[col] = ''
    
    # Get list of README files
    readme_files = [f for f in os.listdir(readme_folder) 
                   if f.endswith('.pdf') and f.startswith('README_AER_')]
    readme_files.sort()  # Process in order
    print(f"Found {len(readme_files)} README files in downloads folder\n")
    
    # Process each README file
    processed_count = 0
    public_data_count = 0
    
    for i, readme_file in enumerate(readme_files, 1):
        paper_id = extract_paper_id_from_filename(readme_file)
        print(f"[{i}/{len(readme_files)}] Processing {paper_id}...")
        
        # Find corresponding row in Excel
        excel_row_idx = find_excel_row_for_paper(df, paper_id, readme_file)
        
        if excel_row_idx is None:
            print(f"  ❌ Could not find matching row in Excel")
            continue
        
        # Read text from README file
        readme_path = os.path.join(readme_folder, readme_file)
        text = read_readme_file(readme_path)
        
        if not text or len(text.strip()) < 50:
            print(f"  ❌ Could not extract sufficient text from README")
            continue
        
        # Analyze with AI
        print(f"  🤖 Analyzing with AI...")
        table_results = analyze_table_data_availability_with_ai(text)
        
        # Update the DataFrame
        if table_results:
            table_count = len(table_results)
            table_summaries = []
            table_identifiers = []
            
            for table in table_results:
                table_id = table.get('table_identifier', 'Unknown')
                table_desc = table.get('table_description', 'No description')
                data_source = table.get('data_source', 'Unknown source')
                confidence = table.get('confidence', 'low')
                
                table_identifiers.append(table_id)
                table_summaries.append(f"{table_id}: {table_desc} | Source: {data_source} | Confidence: {confidence}")
            
            df.loc[excel_row_idx, 'Tables_with_data'] = '; '.join(table_identifiers)
            df.loc[excel_row_idx, 'Table_count'] = table_count
            df.loc[excel_row_idx, 'Table_details'] = ' || '.join(table_summaries)
            
            print(f"  ✅ Found {table_count} table(s) with data: {', '.join(table_identifiers)}")
            public_data_count += table_count
        else:
            df.loc[excel_row_idx, 'Tables_with_data'] = 'None'
            df.loc[excel_row_idx, 'Table_count'] = 0
            df.loc[excel_row_idx, 'Table_details'] = 'No tables with available data found'
            print(f"  ❌ No tables with available data found")
        processed_count += 1
        print()
    
    # Show summary
    print("=" * 50)
    print("SUMMARY RESULTS")
    print("=" * 50)
    print(f"Papers processed: {processed_count}")
    print(f"Total tables with data found: {public_data_count}")
    papers_with_tables = len(df[df['Table_count'] > 0])
    print(f"Papers with tables having data: {papers_with_tables}")
    if processed_count > 0:
        print(f"Percentage of papers with table data: {papers_with_tables/processed_count*100:.1f}%")
    
    # Show detailed breakdown
    table_count_distribution = df['Table_count'].value_counts().sort_index()
    
    print(f"\nTable count distribution:")
    for count, papers in table_count_distribution.items():
        print(f"  {count} tables: {papers} papers")
    
    # Show examples of found tables
    papers_with_data = df[df['Table_count'] > 0]['Tables_with_data'].head(10)
    print(f"\nExample tables found (first 10 papers):")
    for idx, tables in papers_with_data.items():
        print(f"  Paper {idx}: {tables}")
    
    # Save results
    output_file = excel_file.replace('.xlsx', '_with_table_data.xlsx')
    try:
        df.to_excel(output_file, index=False)
        print(f"\n💾 Saved updated file to: {output_file}")
    except Exception as e:
        print(f"❌ Error saving file: {str(e)}")
        # Try backup location
        backup_file = "/Users/paschal/Desktop/AER_MHT/AER_table_data_results.xlsx"
        try:
            df.to_excel(backup_file, index=False)
            print(f"💾 Saved backup file to: {backup_file}")
        except Exception as e2:
            print(f"❌ Error saving backup: {str(e2)}")

if __name__ == "__main__":
    main()