#!/usr/bin/env python3
"""
DIDProcessor - A tool to merge Excel/CSV files and generate numbering files for DIDs.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import sys
from tqdm import tqdm

# Configuration
VALID_EXTENSIONS = {'.xlsx', '.xls', '.csv'}
CSV_ENCODINGS = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']
MEMORY_WARNING_THRESHOLD_MB = 100
OUTPUT_DIR_NAME = 'OUTPUT'

class DIDProcessor:
    """Main class for processing DID files - merging and numbering."""
    
    def __init__(self):
        self.current_dir = Path.cwd()
        self.output_dir = self.current_dir / OUTPUT_DIR_NAME
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        self.client_name = None
        self.dataframes: List[pd.DataFrame] = []
        self.processed_files: List[str] = []
        self.file_stats: List[Dict] = []
        
    def welcome_message(self) -> str:
        """Display welcome message and get user input."""
        ui_config = {
            "title": "DIDProcessor",
            "description": "A tool to Merge and Provide Numbering File for DIDs.",
        }
        
        print("\n" + "=" * 60)
        print(f"📞 {ui_config['title']}")
        print("=" * 60)
        print(ui_config["description"])
        print("-" * 60)
        print("\n📋 Do you want to generate the numbering file?")
        print("   • Enter client name to generate numbering file")
        print("   • Enter 'N' for merge only (no numbering file)")
        print("-" * 60)
        
        user_input = input("➤ ").strip()
        return user_input
    
    def setup_output_directory(self) -> None:
        """Create output directory if it doesn't exist."""
        self.output_dir.mkdir(exist_ok=True)
        print(f"\n📁 Output directory: {self.output_dir}")
    
    def find_compatible_files(self) -> List[Path]:
        """Find all compatible files in current directory."""
        files = [f for f in self.current_dir.iterdir() 
                if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS]
        files.sort()  # Alphabetical sort
        return files
    
    def read_csv_safe(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Read CSV file with multiple encoding attempts."""
        for encoding in CSV_ENCODINGS:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                return df
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"      ⚠️  Error with {encoding}: {str(e)[:50]}...")
                continue
        return None
    
    def read_excel_safe(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Read Excel file with sheet handling."""
        try:
            # Check for multiple sheets
            xl = pd.ExcelFile(file_path)
            if len(xl.sheet_names) > 1:
                print(f"      📑 Multiple sheets found. Using first: '{xl.sheet_names[0]}'")
            return pd.read_excel(file_path)
        except Exception as e:
            print(f"      ❌ Excel read error: {str(e)}")
            return None
    
    def process_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Process a single file and return dataframe."""
        ext = file_path.suffix.lower()
        
        # Read file based on extension
        if ext == '.csv':
            df = self.read_csv_safe(file_path)
        else:
            df = self.read_excel_safe(file_path)
        
        if df is None:
            return None
        
        if df.empty:
            print(f"      ⚠️  File is empty - skipping")
            return None
        
        # Add source tracking for traceability
        df['source_file'] = file_path.name
        
        return df
    
    def check_column_consistency(self) -> Tuple[bool, Dict]:
        """
        Check column consistency across all dataframes.
        Returns (is_consistent, column_report)
        """
        if len(self.dataframes) <= 1:
            return True, {"status": "Single file only"}
        
        reference_cols = set(self.dataframes[0].columns)
        report = {
            "reference_file": self.processed_files[0],
            "reference_columns": sorted(reference_cols),
            "inconsistencies": []
        }
        
        for df, filename in zip(self.dataframes[1:], self.processed_files[1:]):
            current_cols = set(df.columns)
            if current_cols != reference_cols:
                inconsistency = {
                    "file": filename,
                    "missing": sorted(reference_cols - current_cols),
                    "extra": sorted(current_cols - reference_cols)
                }
                report["inconsistencies"].append(inconsistency)
        
        return len(report["inconsistencies"]) == 0, report
    
    def display_column_report(self, is_consistent: bool, report: Dict) -> None:
        """Display column consistency report."""
        print("\n" + "=" * 60)
        print("📊 COLUMN CONSISTENCY REPORT")
        print("=" * 60)
        
        if is_consistent:
            print("✅ All files have identical columns!")
            print(f"   Columns ({len(report['reference_columns'])}): {report['reference_columns']}")
        else:
            print("⚠️  Column inconsistencies detected!")
            print(f"\nReference file: {report['reference_file']}")
            print(f"Reference columns: {report['reference_columns']}")
            
            for inc in report["inconsistencies"]:
                print(f"\n📄 {inc['file']}:")
                if inc['missing']:
                    print(f"   ❌ Missing: {inc['missing']}")
                if inc['extra']:
                    print(f"   ➕ Extra: {inc['extra']}")
        
        print("=" * 60 + "\n")
    
    def excel_merger(self) -> Optional[pd.DataFrame]:
        """Merge all Excel/CSV files with progress tracking."""
        
        # Find files
        files = self.find_compatible_files()
        if not files:
            print(f"\n❌ No compatible files found in: {self.current_dir}")
            print(f"   Supported formats: {', '.join(VALID_EXTENSIONS)}")
            return None
        
        print(f"\n📁 Found {len(files)} file(s) to process")
        
        # Process files with progress bar
        print("\n🔄 Processing files...")
        file_iterator = tqdm(files, desc="Progress", unit="file", 
                            bar_format='{l_bar}{bar:30}{r_bar}')
        
        for file_path in file_iterator:
            file_iterator.set_description(f"Processing {file_path.name[:30]}")
            
            # Process file
            df = self.process_file(file_path)
            
            if df is not None:
                self.dataframes.append(df)
                self.processed_files.append(file_path.name)
                
                # Store stats
                memory_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
                self.file_stats.append({
                    "file": file_path.name,
                    "rows": len(df),
                    "memory_mb": memory_mb
                })
                
                # Warning for large files
                if memory_mb > MEMORY_WARNING_THRESHOLD_MB:
                    tqdm.write(f"      💾 Warning: Large file ({memory_mb:.1f} MB)")
                
                file_iterator.set_postfix({"status": "✅"})
            else:
                file_iterator.set_postfix({"status": "❌"})
        
        # Check if any files were processed
        if not self.dataframes:
            print("\n❌ No valid data found to merge.")
            return None
        
        # Column consistency check
        if len(self.dataframes) > 1:
            is_consistent, report = self.check_column_consistency()
            self.display_column_report(is_consistent, report)
        
        # Merge dataframes
        print("🔗 Merging dataframes...")
        merged_df = pd.concat(self.dataframes, ignore_index=True)
        
        # Generate dynamic filename based on client input
        name_tag = "General" if self.client_name.upper() == 'N' else self.client_name
        output_filename = f'Merged_Data_{name_tag}_{self.timestamp}.xlsx'
        output_path = self.output_dir / output_filename
        
        # Save merged file
        print(f"\n💾 Saving merged file to: {output_filename}")
        merged_df.to_excel(output_path, index=False)
        
        # Display merge summary
        self.display_merge_summary(merged_df, output_path)
        
        return merged_df
    
    def display_merge_summary(self, merged_df: pd.DataFrame, output_path: Path) -> None:
        """Display summary of the merge operation."""
        print("\n" + "=" * 60)
        print("📈 MERGE SUMMARY")
        print("=" * 60)
        
        # Overview
        print(f"📁 Files processed: {len(self.processed_files)}/{len(self.file_stats)}")
        print(f"📊 Total rows: {len(merged_df):,}")
        print(f"📋 Total columns: {len(merged_df.columns)}")
        print(f"💾 Memory usage: {merged_df.memory_usage(deep=True).sum() / (1024 * 1024):.2f} MB")
        
        # Duplicate check
        duplicate_rows = merged_df.duplicated().sum()
        if duplicate_rows > 0:
            dup_pct = (duplicate_rows / len(merged_df)) * 100
            print(f"🔄 Duplicate rows: {duplicate_rows:,} ({dup_pct:.1f}%)")
        
        # Output file info
        if output_path.exists():
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"💾 Output file size: {file_size_mb:.2f} MB")
        
        print("=" * 60)
    

    def generate_numbering_file(self, df: pd.DataFrame, prefix: str = "1") -> None:
        """Generate numbering file from merged data."""
        
        # Check if 'Number' column exists
        if 'Number' not in df.columns:
            print("\n❌ Error: Column 'Number' not found in merged data.")
            print("   Available columns:", list(df.columns))
            return
        
        print("\n" + "=" * 60)
        print("🔢 GENERATING NUMBERING FILE")
        print("=" * 60)
        
        # 1. Clean and transform Number column
        print("🔄 Processing Number column...")
        df_number = df[['Number']].copy().fillna(0).astype(int).astype(str)
        df_number['Number'] = prefix + df_number['Number']
        
        # 2. Rename 'Number' column to 'did'
        df_number = df_number.rename(columns={'Number': 'did'})
        
        # 3. Add metadata columns
        print("📝 Adding metadata...")
        df_number = df_number.assign(
            number_type='did',
            tag=self.client_name,
            customer_tier=1,
            vendor_tier=1
        )
        
        # 4. Generate filename and save
        output_filename = f"Numbering_File_{self.client_name}.csv"
        output_path = self.output_dir / output_filename
        
        print(f"💾 Saving numbering file: {output_filename}")
        df_number.to_csv(output_path, index=False)
        
        # 5. Display numbering file summary
        print("\n📊 Numbering File Summary:")
        print(f"   • Total entries: {len(df_number):,}")
        print(f"   • Prefix applied: '{prefix}'")
        print(f"   • Client tag: '{self.client_name}'")
        print(f"   • Column headers: {list(df_number.columns)}")
        print(f"   • File size: {output_path.stat().st_size / 1024:.1f} KB")
        print(f"\n✅ Numbering file saved successfully!")
        print("=" * 60)
    
    def run(self) -> bool:
        """Main execution method."""
        try:
            # Get user input
            self.client_name = self.welcome_message()
            
            # Setup output directory
            self.setup_output_directory()
            
            # Perform merge
            print("\n" + "=" * 60)
            print("🔄 STARTING MERGE PROCESS")
            print("=" * 60)
            
            merged_data = self.excel_merger()
            
            if merged_data is None:
                print("\n❌ Process stopped: No data to process.")
                return False
            
            # Generate numbering file if requested
            if self.client_name.upper() != 'N':
                print(f"\n📋 Generating numbering file for client: '{self.client_name}'...")
                self.generate_numbering_file(merged_data)
            else:
                print("\nℹ️  Numbering file generation skipped (user opted out).")
            
            print("\n" + "=" * 60)
            print("✅ PROCESS COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            
            return True
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Process interrupted by user")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main entry point."""
    processor = DIDProcessor()
    success = processor.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()