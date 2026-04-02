#!/usr/bin/env python3
"""
DIDMerger - Merge CSV files and generate DID numbering files
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import sys
import re

class DIDMerger:
    def __init__(self):
        self.current_dir = Path.cwd()
        self.output_dir = self.current_dir / 'OUTPUT'
        self.processed_dir = self.current_dir / 'PROCESSED'
        self.client_name = "General"
        self.csv_files = []
        self.merged_df = None
        
    def find_csv_files(self):
        """Find all CSV files in current directory"""
        self.csv_files = list(self.current_dir.glob('*.csv'))
        # Also check for uppercase .CSV
        self.csv_files.extend(list(self.current_dir.glob('*.CSV')))
        # Remove duplicates and sort
        self.csv_files = sorted(list(set(self.csv_files)))
        return self.csv_files
    
    def abbreviate_client_name(self, name: str, max_length: int = 20) -> str:
        """Abbreviate client name if too long - takes first letter of each word"""
        if len(name) <= max_length:
            return name
        
        # Split by spaces and take first letter of each word
        words = name.split()
        abbreviation = ''.join(word[0].upper() for word in words if word)
        
        # If abbreviation is still too long, truncate
        if len(abbreviation) > max_length:
            abbreviation = abbreviation[:max_length]
        
        return abbreviation
    
    def safe_filename(self, name: str) -> str:
        """Remove invalid filename characters"""
        # Remove characters that are invalid in Windows/Linux filenames
        # Invalid: \ / : * ? " < > | and control characters
        safe = re.sub(r'[\\/*?:"<>|]', '', name)
        # Remove any non-printable characters
        safe = ''.join(char for char in safe if char.isprintable())
        # Strip leading/trailing spaces and dots
        safe = safe.strip('. ')
        return safe
    
    def check_columns_consistency(self):
        """Quick check if all CSV files have the same columns"""
        print("\n🔍 Checking column consistency...")
        
        # Get columns from first file
        first_df = pd.read_csv(self.csv_files[0], nrows=0)  # Read only headers
        reference_cols = set(first_df.columns)
        
        # Check if 'Number' column exists
        if 'Number' not in reference_cols:
            print(f"\n❌ Error: 'Number' column not found in the CSV files!")
            print(f"   Found columns: {sorted(reference_cols)}")
            return False
        
        # Check all other files
        for file_path in self.csv_files[1:]:
            current_df = pd.read_csv(file_path, nrows=0)
            current_cols = set(current_df.columns)
            
            if current_cols != reference_cols:
                print(f"\n❌ Columns don't match!")
                print(f"   File: {file_path.name}")
                print(f"   Expected columns: {sorted(reference_cols)}")
                print(f"   Found columns: {sorted(current_cols)}")
                return False
        
        print(f"✅ All {len(self.csv_files)} CSV files have identical columns!")
        print(f"   Columns: {sorted(reference_cols)}")
        return True
    
    def merge_csv_files(self):
        """Merge all CSV files"""
        print("\n📦 Merging CSV files...")
        
        dataframes = []
        for file_path in self.csv_files:
            df = pd.read_csv(file_path)
            dataframes.append(df)
        
        self.merged_df = pd.concat(dataframes, ignore_index=True)
        print(f"✅ Merged {len(self.csv_files)} files into {len(self.merged_df):,} rows")
        return self.merged_df
    
    def save_merged_file(self):
        """Save merged file with required naming format"""
        # Get current date in ISO format
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")  # YYYY-MM-DD format
        
        # Calculate row count
        row_count = len(self.merged_df)
        
        # Process client name
        client_display = self.abbreviate_client_name(self.client_name)
        client_display = self.safe_filename(client_display)
        
        # Create filename with spaces instead of underscores
        filename = f"{client_display} {date_str} {row_count}DIDs.csv"
        
        # Ensure total filename length is under 100 characters
        if len(filename) > 100:
            # Further abbreviate client name
            client_display = self.abbreviate_client_name(self.client_name, max_length=10)
            client_display = self.safe_filename(client_display)
            filename = f"{client_display} {date_str} {row_count}DIDs.csv"
            # If still too long, truncate row count part
            if len(filename) > 100:
                filename = filename[:97] + ".csv"
        
        output_path = self.output_dir / filename
        
        # Save (keeping original 'Number' column name)
        print(f"\n💾 Saving merged file: {filename}")
        self.merged_df.to_csv(output_path, index=False)
        
        # Show file size
        file_size = output_path.stat().st_size / 1024  # KB
        print(f"   Size: {file_size:.1f} KB")
        return output_path
    
    def save_numbering_file(self):
        """Generate and save numbering file"""
        print("\n🔢 Generating numbering file...")
        
        # Check if 'Number' column exists in merged data
        if 'Number' not in self.merged_df.columns:
            print(f"\n❌ Error: 'Number' column not found in merged data!")
            print(f"   Available columns: {list(self.merged_df.columns)}")
            return None
        
        # Create numbering dataframe with only the required columns
        df_number = pd.DataFrame()
        
        # Take the 'Number' column, rename to 'did', clean it, and add prefix
        df_number['did'] = pd.to_numeric(self.merged_df['Number'], errors='coerce').fillna(0).astype(int).astype(str)
        df_number['did'] = '1' + df_number['did']  # Add prefix "1" to all DIDs
        
        # Add the other required columns
        df_number['number_type'] = 'did'
        df_number['tag'] = self.client_name
        df_number['customer_tier'] = 1
        df_number['vendor_tier'] = 1
        
        # Get current date in ISO format
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")  # YYYY-MM-DD format
        
        # Calculate row count
        row_count = len(df_number)
        
        # Process client name
        client_display = self.abbreviate_client_name(self.client_name)
        client_display = self.safe_filename(client_display)
        
        # Create filename with spaces instead of underscores (add NUM for numbering file)
        filename = f"{client_display} NUM {date_str} {row_count}DIDs.csv"
        
        # Ensure total filename length is under 100 characters
        if len(filename) > 100:
            # Further abbreviate client name
            client_display = self.abbreviate_client_name(self.client_name, max_length=8)
            client_display = self.safe_filename(client_display)
            filename = f"{client_display} NUM {date_str} {row_count}DIDs.csv"
            # If still too long, truncate
            if len(filename) > 100:
                filename = filename[:97] + ".csv"
        
        output_path = self.output_dir / filename
        
        # Save
        print(f"💾 Saving numbering file: {filename}")
        df_number.to_csv(output_path, index=False)
        
        # Show file size
        file_size = output_path.stat().st_size / 1024  # KB
        print(f"   Size: {file_size:.1f} KB")
        
        # Show preview of first 10 rows
        print("\n📄 Preview of numbering file (first 10 rows):")
        print(df_number.head(10).to_string(index=False))
        
        return output_path
    
    def move_source_files(self):
        """Move all source CSV files to PROCESSED folder after successful processing"""
        print("\n📦 Organizing source files...")
        
        # Create PROCESSED directory if it doesn't exist
        self.processed_dir.mkdir(exist_ok=True)
        
        moved_count = 0
        for file_path in self.csv_files:
            try:
                # Create destination path
                dest_path = self.processed_dir / file_path.name
                
                # If file already exists in PROCESSED, add timestamp to avoid overwriting
                if dest_path.exists():
                    timestamp = datetime.now().strftime("%H%M%S")
                    new_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
                    dest_path = self.processed_dir / new_name
                    print(f"   ⚠️  File exists, renaming to: {new_name}")
                
                # Move the file
                file_path.rename(dest_path)
                moved_count += 1
                print(f"   ✓ Moved: {file_path.name}")
                
            except Exception as e:
                print(f"   ❌ Could not move {file_path.name}: {str(e)}")
        
        if moved_count > 0:
            print(f"✅ Moved {moved_count} of {len(self.csv_files)} files to PROCESSED folder")
        else:
            print(f"⚠️ No files were moved")
    
    def run(self):
        """Main execution"""
        print("\n" + "=" * 60)
        print("📞 DIDMerger - CSV Merge & Numbering Tool")
        print("=" * 60)
        print("Merge CSV files and generate DID numbering files")
        print("-" * 60)
        
        # 1. Find CSV files
        csv_files = self.find_csv_files()
        if not csv_files:
            print("\n❌ No CSV files found in current directory!")
            return False
        
        print(f"\n📁 Found {len(csv_files)} CSV file(s):")
        for f in csv_files:
            print(f"   • {f.name}")
        
        # 2. Check column consistency
        if not self.check_columns_consistency():
            return False
        
        # 3. Ask for client name
        print("\n" + "-" * 60)
        client_input = input("Enter client name (or press Enter for 'General'): ").strip()
        if client_input:
            self.client_name = client_input
        print(f"✅ Using client name: '{self.client_name}'")
        
        # Show abbreviation if client name is long
        if len(self.client_name) > 20:
            abbr = self.abbreviate_client_name(self.client_name)
            print(f"   ℹ️  Client name will be abbreviated to: '{abbr}' for filename")
        
        # 4. Create output directory
        self.output_dir.mkdir(exist_ok=True)
        print(f"\n📁 Output directory: {self.output_dir}")
        
        # 5. Merge files
        self.merge_csv_files()
        
        # 6. Save merged file (keeps original 'Number' column)
        self.save_merged_file()
        
        # 7. Save numbering file (renames 'Number' to 'did' and adds prefix)
        self.save_numbering_file()
        
        # 8. Move source files to PROCESSED folder
        self.move_source_files()
        
        # 9. Complete
        print("\n" + "=" * 60)
        print("✅ PROCESS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        return True

def main():
    merger = DIDMerger()
    success = merger.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()