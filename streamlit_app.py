"""
🔧 Conti Motors Parts Database Builder
======================================
WITH GOOGLE SHEETS DIRECT INTEGRATION
- Search parts from multiple sources
- Set default part
- Auto-save to Google Sheets
- Track inventory
- Customer lookup by vehicle

Version: 2.0
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime
import json

# Google Sheets imports
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

# Page config
st.set_page_config(
    page_title="Conti Motors - Parts Database",
    page_icon="🔧",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #ff6b35;
        text-align: center;
    }
    .sub-header {
        text-align: center;
        color: #888;
        margin-bottom: 1rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #333;
    }
    .stat-number {
        font-size: 2rem;
        font-weight: bold;
        color: #ff6b35;
    }
    .stat-label {
        color: #888;
        font-size: 0.9rem;
    }
    .connected-badge {
        background: #51cf66;
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .disconnected-badge {
        background: #ff6b6b;
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .alt-tag {
        background: #e8f4f8;
        border: 1px solid #4dabf7;
        color: #1971c2;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        margin: 0.2rem;
        display: inline-block;
        font-family: monospace;
    }
    .oe-tag {
        background: #fff3e6;
        border: 1px solid #ff6b35;
        color: #d9480f;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        margin: 0.2rem;
        display: inline-block;
        font-family: monospace;
    }
    .vehicle-tag {
        background: #e6fcf5;
        border: 1px solid #20c997;
        color: #087f5b;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        margin: 0.2rem;
        display: inline-block;
    }
    .success-box {
        background: #d3f9d8;
        border: 1px solid #51cf66;
        color: #2b8a3e;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .warning-box {
        background: #fff3bf;
        border: 1px solid #ffc107;
        color: #856404;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============ GOOGLE SHEETS FUNCTIONS ============

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_google_sheets_service():
    """Initialize Google Sheets service from Streamlit secrets"""
    try:
        if 'gcp_service_account' not in st.secrets:
            return None
        
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        return service
    except Exception as e:
        st.error(f"Google Sheets connection error: {e}")
        return None


def get_spreadsheet_id():
    """Get spreadsheet ID from secrets"""
    try:
        return st.secrets["spreadsheet"]["spreadsheet_id"]
    except:
        return None


def append_to_sheet(service, spreadsheet_id, sheet_name, values):
    """Append a row to a specific sheet"""
    try:
        body = {'values': [values]}
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A:Z',
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        return True
    except HttpError as e:
        st.error(f"Error writing to sheet: {e}")
        return False


def read_sheet(service, spreadsheet_id, sheet_name):
    """Read all data from a sheet"""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A:Z'
        ).execute()
        values = result.get('values', [])
        if values:
            headers = values[0]
            data = values[1:] if len(values) > 1 else []
            return headers, data
        return [], []
    except HttpError as e:
        return [], []


def initialize_sheet_headers(service, spreadsheet_id):
    """Initialize sheet headers if empty"""
    headers = {
        'Parts_Master': ['Part_ID', 'OE_Number', 'Brand', 'Category', 'Sub_Category', 'Design_Type', 'Description', 'Fits_Models', 'Fits_Years', 'Notes', 'Date_Added'],
        'Alternatives': ['Part_ID', 'OE_Number', 'Alternative_PN', 'Manufacturer', 'Is_Default', 'Price_EUR', 'Price_MYR', 'Source', 'Source_URL', 'Availability', 'Quality_Rating', 'Notes', 'Date_Added'],
        'Inventory': ['Part_ID', 'OE_Number', 'Default_PN', 'Manufacturer', 'Category', 'Qty_In_Stock', 'Min_Stock_Level', 'Max_Stock_Level', 'Location', 'Bin_Number', 'Reorder_Needed', 'Last_Purchase_Date', 'Last_Purchase_Qty', 'Last_Purchase_Price_MYR', 'Supplier', 'Supplier_Contact', 'Notes'],
        'Vehicles': ['Part_ID', 'OE_Number', 'Car_Brand', 'Model', 'Body_Code', 'Generation', 'Year_From', 'Year_To', 'Engine_Code', 'Engine_Size_CC', 'KW', 'HP', 'Fuel_Type', 'Notes']
    }
    
    for sheet_name, header_row in headers.items():
        try:
            existing_headers, _ = read_sheet(service, spreadsheet_id, sheet_name)
            if not existing_headers:
                body = {'values': [header_row]}
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f'{sheet_name}!A1',
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
        except:
            pass


def get_next_part_id(service, spreadsheet_id):
    """Get next part ID from sheet"""
    try:
        _, data = read_sheet(service, spreadsheet_id, 'Parts_Master')
        if data:
            # Get max Part_ID
            max_id = 0
            for row in data:
                if row and row[0].startswith('P'):
                    try:
                        num = int(row[0][1:])
                        max_id = max(max_id, num)
                    except:
                        pass
            return f"P{max_id + 1:04d}"
        return "P0001"
    except:
        return "P0001"


# ============ SEARCH FUNCTIONS ============

CATEGORIES = {
    "Filters": ["Oil Filter", "Air Filter", "Fuel Filter", "Cabin Filter", "Transmission Filter"],
    "Brakes": ["Brake Pads", "Brake Discs", "Brake Sensors", "Brake Calipers", "Brake Lines"],
    "Suspension": ["Control Arms", "Ball Joints", "Tie Rod Ends", "Bushings", "Shock Absorbers", "Springs", "Wheel Bearings"],
    "Engine": ["Spark Plugs", "Ignition Coils", "Belts", "Tensioners", "Gaskets", "Sensors", "Water Pump", "Thermostat"],
    "Cooling": ["Radiator", "Coolant Hoses", "Expansion Tank", "Radiator Fan"],
    "Electrical": ["Starter Motor", "Alternator", "Battery", "Sensors", "Switches"],
    "Steering": ["Tie Rods", "Steering Rack", "Power Steering Pump"],
    "Transmission": ["Clutch Kit", "Flywheel", "Gearbox Mount", "CV Joint", "Drive Shaft"],
    "Exhaust": ["Catalytic Converter", "Muffler", "Exhaust Pipe", "Lambda Sensor"],
    "Body": ["Mirrors", "Lights", "Wipers", "Door Parts"],
}

BRANDS = ["BMW", "Audi", "Mercedes-Benz", "Volkswagen", "Porsche", "Mini"]

@st.cache_resource
def get_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    return session


def generate_search_variations(query):
    """Generate multiple search formats"""
    variations = []
    original = query.strip()
    variations.append(original)
    
    no_spaces = re.sub(r'[\s\-\.\/]', '', original)
    if no_spaces not in variations:
        variations.append(no_spaces)
    
    alphanumeric = re.sub(r'[^a-zA-Z0-9]', '', original)
    if alphanumeric not in variations:
        variations.append(alphanumeric)
    
    upper = no_spaces.upper()
    if upper not in variations:
        variations.append(upper)
    
    return variations


def search_spareto(query):
    """Search Spareto for parts"""
    session = get_session()
    
    variations = generate_search_variations(query)
    
    for search_query in variations:
        clean_query = re.sub(r'[\s\-]', '', search_query)
        url = f"https://spareto.com/oe/{clean_query}"
        
        try:
            response = session.get(url, timeout=20)
            if response.status_code == 404:
                continue
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Check if page has products
            products_found = soup.find_all('a', href=re.compile(r'^/products/[^/]+/[^/]+$'))
            if not products_found:
                continue
            
            result = {
                'query': query,
                'query_used': search_query,
                'url': url,
                'source': 'Spareto',
                'title': '',
                'products': [],
                'oe_numbers': [],
                'vehicles': [],
                'specifications': {}
            }
            
            # Title
            h1 = soup.find('h1')
            if h1:
                result['title'] = h1.get_text(strip=True)
            
            # Products
            seen = set()
            for link in products_found:
                href = link.get('href')
                if href and href not in seen:
                    seen.add(href)
                    part_number = href.split('/')[-1].upper()
                    manufacturer = href.split('/')[-2].replace('-', ' ').title()
                    
                    price = ''
                    parent = link.find_parent(['div', 'li', 'tr'])
                    if parent:
                        m = re.search(r'€\s*([\d,.]+)', parent.get_text())
                        if m:
                            price = m.group(1)
                    
                    result['products'].append({
                        'part_number': part_number,
                        'manufacturer': manufacturer,
                        'price_eur': price,
                        'url': 'https://spareto.com' + href,
                        'source': 'Spareto'
                    })
            
            # OE Numbers
            for link in soup.find_all('a', href=re.compile(r'^/oe/')):
                oe = link.get_text(strip=True)
                if oe and len(oe) > 3 and oe not in result['oe_numbers']:
                    result['oe_numbers'].append(oe)
            
            # Vehicles
            for link in soup.find_all('a', href=re.compile(r'/t/vehicles/')):
                text = link.get_text(strip=True)
                if text and len(text) > 2 and text not in result['vehicles']:
                    result['vehicles'].append(text)
            
            # Specifications
            for table in soup.find_all('table'):
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if label and value and len(label) < 40:
                            skip = ['action', 'price', 'availability', 'check']
                            if not any(x in label.lower() for x in skip):
                                result['specifications'][label] = value
            
            return result
            
        except Exception as e:
            continue
    
    return None


def save_to_google_sheets(service, spreadsheet_id, part_data, alternatives, inventory_info, selected_default):
    """Save part data directly to Google Sheets"""
    
    part_id = get_next_part_id(service, spreadsheet_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Save to Parts_Master
    parts_row = [
        part_id,
        part_data['query'],
        inventory_info['brand'],
        inventory_info['category'],
        inventory_info['sub_category'],
        part_data.get('title', ''),
        part_data.get('title', ''),
        ', '.join(part_data.get('vehicles', [])[:5]),
        '',  # Fits_Years
        '',  # Notes
        today
    ]
    append_to_sheet(service, spreadsheet_id, 'Parts_Master', parts_row)
    
    # 2. Save to Alternatives
    for alt in alternatives:
        is_default = 'Yes' if alt['part_number'] == selected_default else 'No'
        alt_row = [
            part_id,
            part_data['query'],
            alt['part_number'],
            alt['manufacturer'],
            is_default,
            alt.get('price_eur', ''),
            str(inventory_info.get('price_myr', '')),
            alt.get('source', 'Spareto'),
            alt.get('url', ''),
            'In Stock',  # Availability
            '⭐⭐⭐⭐' if is_default == 'Yes' else '',  # Quality
            '',  # Notes
            today
        ]
        append_to_sheet(service, spreadsheet_id, 'Alternatives', alt_row)
    
    # 3. Save to Inventory
    default_alt = next((a for a in alternatives if a['part_number'] == selected_default), alternatives[0] if alternatives else {})
    qty = inventory_info.get('qty', 0)
    min_stock = inventory_info.get('min_stock', 2)
    reorder = 'Yes' if qty < min_stock else 'No'
    
    inv_row = [
        part_id,
        part_data['query'],
        selected_default,
        default_alt.get('manufacturer', ''),
        inventory_info['sub_category'],
        str(qty),
        str(min_stock),
        str(inventory_info.get('max_stock', 10)),
        inventory_info.get('location', ''),
        '',  # Bin
        reorder,
        today,  # Last Purchase Date
        '',  # Last Purchase Qty
        str(inventory_info.get('price_myr', '')),
        inventory_info.get('supplier', ''),
        '',  # Supplier Contact
        ''   # Notes
    ]
    append_to_sheet(service, spreadsheet_id, 'Inventory', inv_row)
    
    # 4. Save to Vehicles
    for vehicle in part_data.get('vehicles', [])[:10]:
        veh_row = [
            part_id,
            part_data['query'],
            inventory_info['brand'],
            vehicle,
            '',  # Body Code
            '',  # Generation
            '',  # Year From
            '',  # Year To
            '',  # Engine Code
            '',  # Engine CC
            '',  # KW
            '',  # HP
            '',  # Fuel
            ''   # Notes
        ]
        append_to_sheet(service, spreadsheet_id, 'Vehicles', veh_row)
    
    return part_id


# ============ UI ============

st.markdown('<h1 class="main-header">🔧 Conti Motors</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Parts Database Builder - Google Sheets Integration</p>', unsafe_allow_html=True)

# Initialize Google Sheets
sheets_service = None
spreadsheet_id = None

if GOOGLE_AVAILABLE:
    sheets_service = get_google_sheets_service()
    spreadsheet_id = get_spreadsheet_id()
    
    if sheets_service and spreadsheet_id:
        # Initialize headers if needed
        initialize_sheet_headers(sheets_service, spreadsheet_id)

# Connection status
col_status1, col_status2, col_status3 = st.columns([1, 2, 1])
with col_status2:
    if sheets_service and spreadsheet_id:
        st.markdown('<p style="text-align:center;"><span class="connected-badge">✅ Connected to Google Sheets</span></p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="text-align:center;"><span class="disconnected-badge">❌ Not Connected - Check Settings</span></p>', unsafe_allow_html=True)
        st.info("👉 Go to 'Settings' tab to configure Google Sheets connection")

# Stats row
if sheets_service and spreadsheet_id:
    _, parts_data = read_sheet(sheets_service, spreadsheet_id, 'Parts_Master')
    _, alt_data = read_sheet(sheets_service, spreadsheet_id, 'Alternatives')
    _, inv_data = read_sheet(sheets_service, spreadsheet_id, 'Inventory')
    
    parts_count = len(parts_data) if parts_data else 0
    alt_count = len(alt_data) if alt_data else 0
    
    total_stock = 0
    reorder_count = 0
    if inv_data:
        for row in inv_data:
            try:
                total_stock += int(row[5]) if len(row) > 5 and row[5] else 0
                if len(row) > 10 and row[10] == 'Yes':
                    reorder_count += 1
            except:
                pass
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{parts_count}</div><div class="stat-label">Parts in DB</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{alt_count}</div><div class="stat-label">Alternatives</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{total_stock}</div><div class="stat-label">Items in Stock</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{reorder_count}</div><div class="stat-label">Need Reorder</div></div>', unsafe_allow_html=True)

st.markdown("---")

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Search & Add", "📦 Database", "📊 Inventory", "🚗 Vehicle Lookup", "⚙️ Settings"])

# TAB 1: Search & Add
with tab1:
    st.markdown("### 🔍 Search for Parts")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            "Enter OE Number or Part Number",
            placeholder="e.g., 11427566327 or HU816X",
            key="search_input",
            label_visibility="collapsed"
        )
    with col2:
        search_btn = st.button("🔍 Search", type="primary", use_container_width=True)
    
    st.caption("💡 Type any format - with or without spaces - we'll find it!")
    
    # Quick examples
    st.markdown("**Quick Examples:**")
    ex_cols = st.columns(6)
    examples = ['11427566327', '34116860242', '04465-47060', '5K0698451A', '1K0615301AA', 'A0004203000']
    for i, ex in enumerate(examples):
        with ex_cols[i]:
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state['auto_search'] = ex
                st.rerun()
    
    # Auto search from button click
    if 'auto_search' in st.session_state:
        search_query = st.session_state['auto_search']
        search_btn = True
        del st.session_state['auto_search']
    
    # Search results
    if search_btn and search_query:
        with st.spinner(f'🔍 Searching for "{search_query}"...'):
            result = search_spareto(search_query)
        
        if not result:
            st.error(f"⚠️ No results found for '{search_query}'")
        else:
            if result.get('query_used') != search_query:
                st.info(f"✅ Found using format: `{result['query_used']}`")
            
            st.success(f"✅ Found: **{result.get('title', search_query)}**")
            st.markdown(f"🔗 [View on {result['source']}]({result['url']})")
            
            # OE Numbers
            if result['oe_numbers']:
                st.markdown("**📋 OE Numbers:**")
                oe_html = ''.join([f'<span class="oe-tag">{oe}</span>' for oe in result['oe_numbers'][:10]])
                st.markdown(oe_html, unsafe_allow_html=True)
            
            # Vehicles
            if result['vehicles']:
                st.markdown("**🚗 Fits Vehicles:**")
                v_html = ''.join([f'<span class="vehicle-tag">{v}</span>' for v in result['vehicles'][:8]])
                st.markdown(v_html, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Alternatives
            if result['products']:
                st.markdown("### 🔄 Alternative Parts - Select Default")
                
                # Radio selection for default
                options = []
                for p in result['products'][:15]:
                    if p['price_eur']:
                        options.append(f"{p['manufacturer']} - {p['part_number']} (€{p['price_eur']})")
                    else:
                        options.append(f"{p['manufacturer']} - {p['part_number']}")
                
                selected_option = st.radio(
                    "Select your default part:",
                    options,
                    index=0,
                    key="default_radio"
                )
                
                # Extract selected part number
                selected_default = selected_option.split(" - ")[1].split(" (")[0] if " - " in selected_option else result['products'][0]['part_number']
                
                # Show table
                alt_df = pd.DataFrame([{
                    '⭐': '⭐ DEFAULT' if f"{p['manufacturer']} - {p['part_number']}" in selected_option else '',
                    'Manufacturer': p['manufacturer'],
                    'Part Number': p['part_number'],
                    'Price (EUR)': f"€{p['price_eur']}" if p['price_eur'] else '-',
                    'Source': p.get('source', 'Spareto')
                } for p in result['products'][:15]])
                
                st.dataframe(alt_df, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                
                # Save form
                st.markdown("### 💾 Save to Google Sheets")
                
                if not sheets_service or not spreadsheet_id:
                    st.warning("⚠️ Google Sheets not connected. Go to Settings tab to configure.")
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        brand = st.selectbox("Car Brand", BRANDS, key="save_brand")
                        category = st.selectbox("Category", list(CATEGORIES.keys()), key="save_cat")
                        sub_category = st.selectbox("Sub-Category", CATEGORIES[category], key="save_subcat")
                        location = st.text_input("Storage Location", placeholder="e.g., Shelf A1", key="save_loc")
                    
                    with col2:
                        qty = st.number_input("Quantity in Stock", min_value=0, value=0, key="save_qty")
                        min_stock = st.number_input("Min Stock Level", min_value=0, value=2, key="save_min")
                        max_stock = st.number_input("Max Stock Level", min_value=0, value=10, key="save_max")
                        price_myr = st.number_input("Your Price (MYR)", min_value=0.0, value=0.0, key="save_price")
                        supplier = st.text_input("Supplier", placeholder="e.g., AutoParts MY", key="save_supplier")
                    
                    if st.button("💾 Save to Google Sheets", type="primary", use_container_width=True):
                        inventory_info = {
                            'brand': brand,
                            'category': category,
                            'sub_category': sub_category,
                            'location': location,
                            'qty': qty,
                            'min_stock': min_stock,
                            'max_stock': max_stock,
                            'price_myr': price_myr,
                            'supplier': supplier
                        }
                        
                        with st.spinner("Saving to Google Sheets..."):
                            part_id = save_to_google_sheets(
                                sheets_service,
                                spreadsheet_id,
                                result,
                                result['products'][:15],
                                inventory_info,
                                selected_default
                            )
                        
                        st.markdown(f"""
                        <div class="success-box">
                            ✅ <strong>Saved to Google Sheets!</strong><br>
                            Part ID: <strong>{part_id}</strong><br>
                            OE Number: {search_query}<br>
                            Default Part: {selected_default}<br>
                            {len(result['products'][:15])} alternatives saved
                        </div>
                        """, unsafe_allow_html=True)
                        st.balloons()

# TAB 2: Database View
with tab2:
    st.markdown("### 📦 Parts Database")
    
    if not sheets_service or not spreadsheet_id:
        st.warning("⚠️ Google Sheets not connected.")
    else:
        # Refresh button
        if st.button("🔄 Refresh Data"):
            st.rerun()
        
        # Parts Master
        st.markdown("#### Parts Master")
        headers, data = read_sheet(sheets_service, spreadsheet_id, 'Parts_Master')
        if data:
            df = pd.DataFrame(data, columns=headers if headers else None)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No parts in database yet.")
        
        # Alternatives
        st.markdown("#### Alternatives / Cross-References")
        headers, data = read_sheet(sheets_service, spreadsheet_id, 'Alternatives')
        if data:
            df = pd.DataFrame(data, columns=headers if headers else None)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No alternatives yet.")

# TAB 3: Inventory
with tab3:
    st.markdown("### 📊 Inventory Status")
    
    if not sheets_service or not spreadsheet_id:
        st.warning("⚠️ Google Sheets not connected.")
    else:
        headers, data = read_sheet(sheets_service, spreadsheet_id, 'Inventory')
        if data:
            df = pd.DataFrame(data, columns=headers if headers else None)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Reorder alerts
            reorder_items = [row for row in data if len(row) > 10 and row[10] == 'Yes']
            if reorder_items:
                st.markdown("---")
                st.warning(f"⚠️ **{len(reorder_items)} items need reordering!**")
                for item in reorder_items:
                    st.markdown(f"- **{item[2]}** ({item[4]}) - Stock: {item[5]}, Min: {item[6]}")
        else:
            st.info("No inventory data yet.")

# TAB 4: Vehicle Lookup
with tab4:
    st.markdown("### 🚗 Find Parts by Vehicle")
    st.caption("Select a vehicle to see all parts in your database that fit it.")
    
    if not sheets_service or not spreadsheet_id:
        st.warning("⚠️ Google Sheets not connected.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            lookup_brand = st.selectbox("Car Brand", ["All"] + BRANDS, key="lookup_brand")
        with col2:
            lookup_model = st.text_input("Model (optional)", placeholder="e.g., 3 Series, A4", key="lookup_model")
        with col3:
            lookup_btn = st.button("🔍 Find Parts", type="primary", use_container_width=True)
        
        if lookup_btn:
            # Read vehicles sheet
            headers, veh_data = read_sheet(sheets_service, spreadsheet_id, 'Vehicles')
            headers_inv, inv_data = read_sheet(sheets_service, spreadsheet_id, 'Inventory')
            
            if veh_data:
                # Filter by brand and model
                matching_parts = []
                for row in veh_data:
                    if len(row) >= 4:
                        car_brand = row[2] if len(row) > 2 else ''
                        model = row[3] if len(row) > 3 else ''
                        
                        brand_match = lookup_brand == "All" or car_brand == lookup_brand
                        model_match = not lookup_model or lookup_model.lower() in model.lower()
                        
                        if brand_match and model_match:
                            matching_parts.append({
                                'Part_ID': row[0],
                                'OE_Number': row[1],
                                'Car_Brand': car_brand,
                                'Model': model
                            })
                
                if matching_parts:
                    st.success(f"✅ Found {len(matching_parts)} parts for this vehicle:")
                    
                    # Get inventory info for each part
                    inv_dict = {}
                    if inv_data:
                        for row in inv_data:
                            if len(row) > 5:
                                inv_dict[row[0]] = {
                                    'Default_PN': row[2] if len(row) > 2 else '',
                                    'Category': row[4] if len(row) > 4 else '',
                                    'Qty': row[5] if len(row) > 5 else '0',
                                    'Location': row[8] if len(row) > 8 else ''
                                }
                    
                    # Display results
                    results = []
                    seen_parts = set()
                    for part in matching_parts:
                        if part['Part_ID'] not in seen_parts:
                            seen_parts.add(part['Part_ID'])
                            inv = inv_dict.get(part['Part_ID'], {})
                            results.append({
                                'Part ID': part['Part_ID'],
                                'OE Number': part['OE_Number'],
                                'Default PN': inv.get('Default_PN', ''),
                                'Category': inv.get('Category', ''),
                                'In Stock': inv.get('Qty', '0'),
                                'Location': inv.get('Location', '')
                            })
                    
                    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
                else:
                    st.info("No parts found for this vehicle in your database.")
            else:
                st.info("No vehicle data in database yet.")

# TAB 5: Settings
with tab5:
    st.markdown("### ⚙️ Google Sheets Settings")
    
    st.markdown("""
    To connect to Google Sheets, you need to add secrets to your Streamlit app.
    
    #### For Streamlit Cloud:
    
    1. Go to your app on [share.streamlit.io](https://share.streamlit.io)
    2. Click **"Settings"** (⚙️) → **"Secrets"**
    3. Paste the following (replace with your values):
    """)
    
    st.code("""
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\\nYOUR_PRIVATE_KEY_HERE\\n-----END PRIVATE KEY-----\\n"
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your-cert-url"

[spreadsheet]
spreadsheet_id = "YOUR_SPREADSHEET_ID_HERE"
    """, language="toml")
    
    st.markdown("""
    #### How to get these values:
    
    1. **gcp_service_account**: Open the JSON file you downloaded from Google Cloud
       - Copy all the values from the JSON file
       
    2. **spreadsheet_id**: From your Google Sheet URL
       - `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`
    
    ---
    
    #### Current Status:
    """)
    
    if sheets_service and spreadsheet_id:
        st.success("✅ Connected to Google Sheets!")
        st.markdown(f"**Spreadsheet ID:** `{spreadsheet_id[:20]}...`")
    else:
        st.error("❌ Not connected. Please add secrets above.")
    
    st.markdown("---")
    st.markdown("#### Test Connection")
    if st.button("🔄 Test Connection"):
        if sheets_service and spreadsheet_id:
            try:
                headers, _ = read_sheet(sheets_service, spreadsheet_id, 'Parts_Master')
                st.success(f"✅ Connection successful! Found sheets with headers.")
            except Exception as e:
                st.error(f"❌ Connection failed: {e}")
        else:
            st.error("❌ Not configured. Add secrets first.")

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #666;'>© 2025 Conti Motors • Seremban, Malaysia</p>",
    unsafe_allow_html=True
)
