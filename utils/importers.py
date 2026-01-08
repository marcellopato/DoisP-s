
import xml.etree.ElementTree as ET
from datetime import datetime
import re
import pandas as pd

def parse_excel_xml(file_content):
    """
    Parses an Excel 2003 XML file to extract debts and expenses.
    
    Args:
        file_content: The content of the XML file (bytes or string).
        
    Returns:
        dict: A dictionary containing 'debts' and 'recurring_expenses' lists.
    """
    try:
        # Define namespaces
        namespaces = {
            'ss': 'urn:schemas-microsoft-com:office:spreadsheet',
            'o': 'urn:schemas-microsoft-com:office:office',
            'x': 'urn:schemas-microsoft-com:office:excel',
            'html': 'http://www.w3.org/TR/REC-html40'
        }
        
        root = ET.fromstring(file_content)
        
        # Find the first worksheet
        worksheet = root.find('.//ss:Worksheet', namespaces)
        if worksheet is None:
            return {"error": "No worksheet found"}
            
        table = worksheet.find('.//ss:Table', namespaces)
        if table is None:
            return {"error": "No table found"}
            
        rows = table.findall('.//ss:Row', namespaces)
        
        items = []
        
        # Skip header if present (simplified heuristic: checks if first row has "DÍVIDAS" or similar)
        start_row_index = 0
        first_row_cells = rows[0].findall('.//ss:Cell', namespaces)
        if first_row_cells and first_row_cells[0].find('.//ss:Data', namespaces).text.strip().upper() in ['DÍVIDAS', 'DESCRIÇÃO']:
            start_row_index = 1
            
        for row in rows[start_row_index:]:
            cells = row.findall('.//ss:Cell', namespaces)
            if not cells:
                continue
                
            # Helper to get cell data safely
            def get_cell_data(index, type_conversion=None):
                if index < len(cells):
                    data_elem = cells[index].find('.//ss:Data', namespaces)
                    if data_elem is not None and data_elem.text:
                        val = data_elem.text
                        if type_conversion:
                            try:
                                return type_conversion(val)
                            except:
                                return None
                        return val
                return None

            # Mapping based on DIVIDAS-GIGI.xml structure:
            # Cell 0: Description
            # Cell 1: Total Value / Installment Value
            # Cell 2: Date
            # Cell 3: Entry Value (optional) OR Installment Details (if misplaced)
            # Cell 4: Installment Details (optional)
            
            description = get_cell_data(0, str)
            value = get_cell_data(1, float)
            date_str = get_cell_data(2, str)
            
            col3_raw = get_cell_data(3, str)
            col4_raw = get_cell_data(4, str)
            
            entry_value = None
            installment_details = None
            
            # Heuristic to find Installment Details ("999 x 9" pattern)
            def is_installment_str(s):
                return s and 'x' in str(s).lower() and any(c.isdigit() for c in str(s))
            
            if is_installment_str(col4_raw):
                installment_details = col4_raw
                # Try to parse entry value from col3 if it's a number
                try:
                    entry_value = float(col3_raw)
                except:
                    pass
            elif is_installment_str(col3_raw):
                # Misplaced installment details in col3
                installment_details = col3_raw
                entry_value = None
            else:
                # No installments found, try to parse col3 as entry value
                if col3_raw:
                    try:
                        entry_value = float(col3_raw)
                    except:
                        pass
            
            if not description or value is None:
                continue
                
            # Parse Date
            date_obj = None
            if date_str:
                try:
                    # Excel XML dates are usually ISO format 2026-01-19T00:00:00.000
                    date_obj = datetime.fromisoformat(date_str).date()
                except ValueError:
                    pass
            
            item = {
                "description": description,
                "value": value,
                "date": date_obj,
                "entry_value": entry_value,
                "installment_details": installment_details,
                "type": "undefined"
            }
            
            # Logic to distinguish Debt vs Recurring vs One-time
            # If it has installment details (e.g., "x 2"), it's likely a Debt installment plan
            if installment_details and 'x' in installment_details.lower():
                item["type"] = "debt"
                # Parse "964,00 x 2" -> Value per installment X Num installments
                try:
                    parts = installment_details.lower().split('x')
                    inst_val_str = parts[0].strip().replace('.','').replace(',','.')
                    num_inst = int(parts[1].strip())
                    item["installments_count"] = num_inst
                    item["installment_value"] = float(inst_val_str) if inst_val_str else value
                except:
                    item["installments_count"] = 1
                    item["installment_value"] = value
            elif date_obj and date_obj.day <= 10: # Heuristic: bills usually due early month
                item["type"] = "recurring"
            else:
                item["type"] = "expense" # Default to single expense
                
            items.append(item)
            
        return {"items": items}

    except Exception as e:
        return {"error": str(e)}
