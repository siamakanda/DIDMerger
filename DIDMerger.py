#!/usr/bin/env python3
"""
DIDMerger - Merge CSV files and generate DID numbering files
"""

import csv
import os
import sys
import re
from pathlib import Path
from datetime import datetime


class DIDMerger:
    def __init__(self):
        self.current_dir = Path.cwd()
        self.output_dir = self.current_dir / 'OUTPUT'
        self.processed_dir = self.current_dir / 'PROCESSED'
        self.client_name = "General"
        self.csv_files = []
        self.merged_rows = []

    def find_csv_files(self):
        """Find all CSV files in current directory"""
        self.csv_files = list(self.current_dir.glob('*.csv'))
        self.csv_files.extend(list(self.current_dir.glob('*.CSV')))
        self.csv_files = sorted(list(set(self.csv_files)))
        return self.csv_files

    def read_csv(self, filepath):
        """Read a CSV file and return (headers, rows) where rows is a list of dicts"""
        with open(filepath, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)
        return headers, rows

    def write_csv(self, filepath, headers, rows):
        """Write rows (list of dicts) to a CSV file"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    def abbreviate_client_name(self, name, max_length=20):
        """Abbreviate client name if too long"""
        if len(name) <= max_length:
            return name
        abbreviation = ''.join(word[0].upper() for word in name.split() if word)
        if len(abbreviation) > max_length:
            abbreviation = abbreviation[:max_length]
        return abbreviation

    def safe_filename(self, name):
        """Remove invalid filename characters"""
        safe = re.sub(r'[\\/*?:"<>|]', '', name)
        safe = ''.join(char for char in safe if char.isprintable())
        safe = safe.strip('. ')
        return safe

    def check_columns_consistency(self):
        """Quick check if all CSV files have the same columns"""
        print("\n[CHECK] Checking column consistency...")

        headers, _ = self.read_csv(self.csv_files[0])
        reference_cols = set(headers)

        for file_path in self.csv_files[1:]:
            current_headers, _ = self.read_csv(file_path)
            current_cols = set(current_headers)
            if current_cols != reference_cols:
                print(f"\n[ERROR] Columns don't match!")
                print(f"        File: {file_path.name}")
                print(f"        Expected columns: {sorted(reference_cols)}")
                print(f"        Found columns: {sorted(current_cols)}")
                return False

        print(f"[OK] All {len(self.csv_files)} CSV files have identical columns!")
        print(f"     Columns: {sorted(reference_cols)}")
        return True

    def merge_csv_files(self):
        """Merge all CSV files into self.merged_rows"""
        print("\n[MERGE] Merging CSV files...")

        all_rows = []
        for file_path in self.csv_files:
            _, rows = self.read_csv(file_path)
            all_rows.extend(rows)

        self.merged_rows = all_rows
        print(f"[OK] Merged {len(self.csv_files)} files into {len(self.merged_rows):,} rows")
        return self.merged_rows

    @property
    def merged_headers(self):
        """Get headers from the first CSV file (must be called after merge)"""
        if self.csv_files:
            headers, _ = self.read_csv(self.csv_files[0])
            return headers
        return []

    def save_merged_file(self):
        """Save merged file with required naming format"""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        row_count = len(self.merged_rows)

        client_display = self.abbreviate_client_name(self.client_name)
        client_display = self.safe_filename(client_display)

        filename = f"{client_display} {date_str} {row_count}DIDs.csv"

        if len(filename) > 100:
            client_display = self.abbreviate_client_name(self.client_name, max_length=10)
            client_display = self.safe_filename(client_display)
            filename = f"{client_display} {date_str} {row_count}DIDs.csv"
            if len(filename) > 100:
                filename = filename[:97] + ".csv"

        output_path = self.output_dir / filename
        headers = self.merged_headers

        print(f"\n[SAVE] Saving merged file: {filename}")
        self.write_csv(output_path, headers, self.merged_rows)

        file_size = output_path.stat().st_size / 1024
        print(f"       Size: {file_size:.1f} KB")
        return output_path

    @staticmethod
    def clean_number(value):
        """Convert a value to a clean numeric string, or return None"""
        if value is None:
            return None
        s = str(value).strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not s:
            return None
        s = re.sub(r'[^\d]', '', s)
        if not s:
            return None
        return s

    def detect_did_numbers(self):
        """Scan all rows for 10 or 11 digit numbers to use as DIDs"""
        print("\n[CHECK] Scanning for DID numbers...")
        headers = self.merged_headers

        did_numbers = []
        source_columns = {}

        for col in headers:
            found_in_col = []
            for row in self.merged_rows:
                value = row.get(col, '')
                if not value or str(value).strip() == '':
                    continue
                cleaned = self.clean_number(value)
                if cleaned is None:
                    continue

                if len(cleaned) == 10:
                    did_numbers.append(cleaned)
                    found_in_col.append(cleaned)
                elif len(cleaned) == 11:
                    if cleaned.startswith('1'):
                        did_numbers.append(cleaned[1:])
                        found_in_col.append(f"{cleaned} -> {cleaned[1:]}")
                    else:
                        did_numbers.append(cleaned)
                        found_in_col.append(cleaned)

            if found_in_col:
                source_columns[col] = len(found_in_col)

        # Deduplicate preserving order
        seen = set()
        unique_dids = []
        for did in did_numbers:
            if did not in seen:
                seen.add(did)
                unique_dids.append(did)

        if source_columns:
            print(f"[OK] Found {len(unique_dids)} unique DID numbers:")
            for col_name, count in list(source_columns.items())[:5]:
                print(f"     - Column '{col_name}': Found {count} numbers")
            if len(source_columns) > 5:
                print(f"     - ... and {len(source_columns) - 5} more columns")
        else:
            print("[ERROR] No 10 or 11 digit numbers found in any column!")
            return None

        return unique_dids

    def save_numbering_file(self):
        """Generate and save numbering file"""
        print("\n[NUM] Generating numbering file...")
        headers = self.merged_headers

        if 'Number' in headers:
            print("[OK] Using 'Number' column for DIDs")
            source_numbers = []
            for row in self.merged_rows:
                val = row.get('Number', '')
                if val and str(val).strip():
                    source_numbers.append(str(val).strip())
        else:
            print("[WARN] 'Number' column not found!")
            print("       Scanning all columns for 10 or 11 digit numbers...")

            detected_dids = self.detect_did_numbers()

            if detected_dids is None:
                print("\n[ERROR] No valid DID numbers found in any column!")
                print("        Please ensure your CSV files contain a 'Number' column")
                print("        or 10/11 digit phone numbers in other columns.")
                return None

            source_numbers = detected_dids
            print(f"\n[OK] Using {len(source_numbers)} detected DIDs for numbering file")

        # Build numbering rows
        numbering_headers = ['number', 'mrc', 'nrc', 'route_type', 'max_channels',
                             'ani_mode', 'ani_value', 'dnis_mode', 'dnis_value']
        numbering_rows = []

        for num in source_numbers:
            cleaned = self.clean_number(num)
            if not cleaned:
                continue
            if len(cleaned) < 10:
                continue
            if len(cleaned) > 11:
                cleaned = cleaned[-10:]
            if len(cleaned) == 11 and cleaned.startswith('1'):
                cleaned = cleaned[1:]

            row = {
                'number': '1' + cleaned,
                'mrc': '0',
                'nrc': '0',
                'route_type': 'trunk',
                'max_channels': '100',
                'ani_mode': 'off',
                'ani_value': '',
                'dnis_mode': 'off',
                'dnis_value': '',
            }
            numbering_rows.append(row)

        # Filter rows with valid length
        numbering_rows = [r for r in numbering_rows if len(r['number']) >= 11]

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        row_count = len(numbering_rows)

        client_display = self.abbreviate_client_name(self.client_name)
        client_display = self.safe_filename(client_display)

        filename = f"{client_display} NUM {date_str} {row_count}DIDs.csv"

        if len(filename) > 100:
            client_display = self.abbreviate_client_name(self.client_name, max_length=8)
            client_display = self.safe_filename(client_display)
            filename = f"{client_display} NUM {date_str} {row_count}DIDs.csv"
            if len(filename) > 100:
                filename = filename[:97] + ".csv"

        output_path = self.output_dir / filename

        print(f"\n[SAVE] Saving numbering file: {filename}")
        self.write_csv(output_path, numbering_headers, numbering_rows)

        file_size = output_path.stat().st_size / 1024
        print(f"       Size: {file_size:.1f} KB")

        # Preview
        print("\n[PREVIEW] Numbering file (first 5 rows):")
        for row in numbering_rows[:5]:
            print(f"          {dict(row)}")

        return output_path

    def move_source_files(self):
        """Move all source CSV files to PROCESSED folder after successful processing"""
        print("\n[ORGANIZE] Moving source files to PROCESSED...")

        self.processed_dir.mkdir(exist_ok=True)

        moved_count = 0
        for file_path in self.csv_files:
            try:
                dest_path = self.processed_dir / file_path.name
                if dest_path.exists():
                    timestamp = datetime.now().strftime("%H%M%S")
                    new_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
                    dest_path = self.processed_dir / new_name
                    print(f"          [WARN] File exists, renaming to: {new_name}")

                file_path.rename(dest_path)
                moved_count += 1
                print(f"          Moved: {file_path.name}")

            except Exception as e:
                print(f"          [ERROR] Could not move {file_path.name}: {str(e)}")

        if moved_count > 0:
            print(f"[OK] Moved {moved_count} of {len(self.csv_files)} files to PROCESSED folder")
        else:
            print(f"[WARN] No files were moved")

    def run(self):
        """Main execution"""
        print("\n" + "=" * 60)
        print("  DIDMerger - CSV Merge & Numbering Tool")
        print("=" * 60)
        print("  Merge CSV files and generate DID numbering files")
        print("-" * 60)

        # 1. Find CSV files
        csv_files = self.find_csv_files()
        if not csv_files:
            print("\n[ERROR] No CSV files found in current directory!")
            return False

        print(f"\n[DIR] Found {len(csv_files)} CSV file(s):")
        for f in csv_files:
            print(f"      - {f.name}")

        # 2. Check column consistency
        if not self.check_columns_consistency():
            return False

        # 3. Ask for client name
        print("\n" + "-" * 60)
        client_input = input("Enter client name (or press Enter for 'General'): ").strip()
        if client_input:
            self.client_name = client_input
        print(f"[OK] Using client name: '{self.client_name}'")

        if len(self.client_name) > 20:
            abbr = self.abbreviate_client_name(self.client_name)
            print(f"     [INFO] Client name abbreviated to: '{abbr}' for filename")

        # 4. Create output directory
        self.output_dir.mkdir(exist_ok=True)
        print(f"\n[DIR] Output directory: {self.output_dir}")

        # 5. Merge files
        self.merge_csv_files()

        # 6. Save merged file
        self.save_merged_file()

        # 7. Save numbering file
        self.save_numbering_file()

        # 8. Move source files to PROCESSED folder
        self.move_source_files()

        # 9. Complete
        print("\n" + "=" * 60)
        print("  PROCESS COMPLETED SUCCESSFULLY!")
        print("=" * 60)

        return True


def main():
    merger = DIDMerger()
    success = merger.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
