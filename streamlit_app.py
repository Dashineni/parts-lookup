"""
🔧 Conti Motors Parts Database Builder
======================================
WITH GOOGLE SHEETS DIRECT INTEGRATION
FIXED: Better error handling for sheet data

Version: 2.2
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
</style>
""", unsafe_allow_html=True)

# ============ SESSION STATE INITIALIZATION ============
if 'search_result' not in st.session_state:
    st.session_state.search_result = None
if 'save_success' not in st.session_state:
    st.session_state.save_success = None

# ============ GOOGLE SHEETS FUNCTIONS ============

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

@st.cache_resource
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
        service.spreadsheets().values().append(
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


def read_sheet_as_df(service, spreadsheet_id, sheet_name):
    """Read sheet and return as DataFrame with proper error handling"""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A:Z'
        ).execute()
        values = result.get('values', [])
        
        if not values:
            return pd.DataFrame()
        
        headers = values[0]
        data = values[1:] if len(values) > 1 else []
        
        if not data:
            return pd.DataFrame(columns=headers)
        
        # Normalize rows to have same length as headers
        normalized_data = []
        for row in data:
            # Pad row with empty strings if shorter than headers
            if len(row) < len(headers):
                row = row + [''] * (len(headers) - len(row))
            # Truncate if longer than headers
            elif len(row) > len(headers):
                row = row[:len(headers)]
            normalized_data.append(row)
        
        df = pd.DataFrame(normalized_data, columns=headers)
        return df
        
    except Exception as e:
        st.error(f"Error reading sheet: {e}")
        return pd.DataFrame()


def read_sheet_raw(service, spreadsheet_id, sheet_name):
    """Read raw data from sheet"""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A:Z'
        ).execute()
        values = result.get('values', [])
        
        if not values:
            return [], []
        
        headers = values[0]
        data = values[1:] if len(values) > 1 else []
        return headers, data
        
    except Exception as e:
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
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f'{sheet_name}!A1:Z1'
            ).execute()
            existing = result.get('values', [])
            
            if not existing or not existing[0]:
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
        _, data = read_sheet_raw(service, spreadsheet_id, 'Parts_Master')
        if data:
            max_id = 0
            for row in data:
                if row and len(row) > 0 and row[0].startswith('P'):
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
            
            h1 = soup.find('h1')
            if h1:
                result['title'] = h1.get_text(strip=True)
            
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
            
            for link in soup.find_all('a', href=re.compile(r'^/oe/')):
                oe = link.get_text(strip=True)
                if oe and len(oe) > 3 and oe not in result['oe_numbers']:
                    result['oe_numbers'].append(oe)
            
            for link in soup.find_all('a', href=re.compile(r'/t/vehicles/')):
                text = link.get_text(strip=True)
                if text and len(text) > 2 and text not in result['vehicles']:
                    result['vehicles'].append(text)
            
            return result
            
        except Exception as e:
            continue
    
    return None


def save_to_google_sheets(service, spreadsheet_id, part_data, alternatives, inventory_info, selected_default):
    """Save part data directly to Google Sheets"""
    
    part_id = get_next_part_id(service, spreadsheet_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Save to Parts_Master (11 columns)
    parts_row = [
        part_id,                                    # Part_ID
        part_data['query'],                         # OE_Number
        inventory_info['brand'],                    # Brand
        inventory_info['category'],                 # Category
        inventory_info['sub_category'],             # Sub_Category
        part_data.get('title', ''),                 # Design_Type
        part_data.get('title', ''),                 # Description
        ', '.join(part_data.get('vehicles', [])[:5]), # Fits_Models
        '',                                         # Fits_Years
        '',                                         # Notes
        today                                       # Date_Added
    ]
    append_to_sheet(service, spreadsheet_id, 'Parts_Master', parts_row)
    
    # 2. Save to Alternatives (13 columns)
    for alt in alternatives:
        is_default = 'Yes' if alt['part_number'] == selected_default else 'No'
        alt_row = [
            part_id,                                # Part_ID
            part_data['query'],                     # OE_Number
            alt['part_number'],                     # Alternative_PN
            alt['manufacturer'],                    # Manufacturer
            is_default,                             # Is_Default
            alt.get('price_eur', ''),               # Price_EUR
            str(inventory_info.get('price_myr', '')), # Price_MYR
            alt.get('source', 'Spareto'),           # Source
            alt.get('url', ''),                     # Source_URL
            'In Stock',                             # Availability
            '⭐⭐⭐⭐' if is_default == 'Yes' else '', # Quality_Rating
            '',                                     # Notes
            today                                   # Date_Added
        ]
        append_to_sheet(service, spreadsheet_id, 'Alternatives', alt_row)
    
    # 3. Save to Inventory (17 columns)
    default_alt = next((a for a in alternatives if a['part_number'] == selected_default), alternatives[0] if alternatives else {})
    qty = inventory_info.get('qty', 0)
    min_stock = inventory_info.get('min_stock', 2)
    reorder = 'Yes' if qty < min_stock else 'No'
    
    inv_row = [
        part_id,                                    # Part_ID
        part_data['query'],                         # OE_Number
        selected_default,                           # Default_PN
        default_alt.get('manufacturer', ''),        # Manufacturer
        inventory_info['sub_category'],             # Category
        str(qty),                                   # Qty_In_Stock
        str(min_stock),                             # Min_Stock_Level
        str(inventory_info.get('max_stock', 10)),   # Max_Stock_Level
        inventory_info.get('location', ''),         # Location
        '',                                         # Bin_Number
        reorder,                                    # Reorder_Needed
        today,                                      # Last_Purchase_Date
        '',                                         # Last_Purchase_Qty
        str(inventory_info.get('price_myr', '')),   # Last_Purchase_Price_MYR
        inventory_info.get('supplier', ''),         # Supplier
        '',                                         # Supplier_Contact
        ''                                          # Notes
    ]
    append_to_sheet(service, spreadsheet_id, 'Inventory', inv_row)
    
    # 4. Save to Vehicles (14 columns)
    for vehicle in part_data.get('vehicles', [])[:10]:
        veh_row = [
            part_id,                                # Part_ID
            part_data['query'],                     # OE_Number
            inventory_info['brand'],                # Car_Brand
            vehicle,                                # Model
            '',                                     # Body_Code
            '',                                     # Generation
            '',                                     # Year_From
            '',                                     # Year_To
            '',                                     # Engine_Code
            '',                                     # Engine_Size_CC
            '',                                     # KW
            '',                                     # HP
            '',                                     # Fuel_Type
            ''                                      # Notes
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
        initialize_sheet_headers(sheets_service, spreadsheet_id)

# Connection status
col_status1, col_status2, col_status3 = st.columns([1, 2, 1])
with col_status2:
    if sheets_service and spreadsheet_id:
        st.markdown('<p style="text-align:center;"><span class="connected-badge">✅ Connected to Google Sheets</span></p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="text-align:center;"><span class="disconnected-badge">❌ Not Connected</span></p>', unsafe_allow_html=True)

# Stats row
if sheets_service and spreadsheet_id:
    try:
        parts_df = read_sheet_as_df(sheets_service, spreadsheet_id, 'Parts_Master')
        alt_df = read_sheet_as_df(sheets_service, spreadsheet_id, 'Alternatives')
        inv_df = read_sheet_as_df(sheets_service, spreadsheet_id, 'Inventory')
        
        parts_count = len(parts_df) if not parts_df.empty else 0
        alt_count = len(alt_df) if not alt_df.empty else 0
        
        total_stock = 0
        reorder_count = 0
        if not inv_df.empty and 'Qty_In_Stock' in inv_df.columns:
            for _, row in inv_df.iterrows():
                try:
                    total_stock += int(row.get('Qty_In_Stock', 0) or 0)
                    if row.get('Reorder_Needed') == 'Yes':
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
    except Exception as e:
        st.warning(f"Could not load stats: {e}")

st.markdown("---")

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Search & Add", "📦 Database", "📊 Inventory", "🚗 Vehicle Lookup", "⚙️ Settings"])

# TAB 1: Search & Add
with tab1:
    st.markdown("### 🔍 Search for Parts")
    
    # Search form
    with st.form(key="search_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input(
                "Enter OE Number or Part Number",
                placeholder="e.g., 11427566327 or HU816X",
                label_visibility="collapsed"
            )
        with col2:
            search_btn = st.form_submit_button("🔍 Search", type="primary", use_container_width=True)
    
    st.caption("💡 Type any format - with or without spaces")
    
    # Quick examples
    st.markdown("**Quick Examples:**")
    ex_cols = st.columns(6)
    examples = ['11427566327', '34116860242', '04465-47060', '5K0698451A', '1K0615301AA', 'A0004203000']
    for i, ex in enumerate(examples):
        with ex_cols[i]:
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state.search_result = search_spareto(ex)
                st.session_state.save_success = None
                st.rerun()
    
    # Perform search
    if search_btn and search_query:
        with st.spinner(f'🔍 Searching for "{search_query}"...'):
            st.session_state.search_result = search_spareto(search_query)
            st.session_state.save_success = None
    
    # Show success message
    if st.session_state.save_success:
        st.markdown(f"""
        <div class="success-box">
            ✅ <strong>Saved to Google Sheets!</strong><br>
            Part ID: <strong>{st.session_state.save_success['part_id']}</strong><br>
            OE Number: {st.session_state.save_success['oe_number']}<br>
            Default Part: {st.session_state.save_success['default_pn']}<br>
            {st.session_state.save_success['alt_count']} alternatives saved
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔍 Search for another part"):
            st.session_state.search_result = None
            st.session_state.save_success = None
            st.rerun()
    
    # Display search results
    elif st.session_state.search_result:
        result = st.session_state.search_result
        
        if result.get('query_used') != result.get('query'):
            st.info(f"✅ Found using format: `{result['query_used']}`")
        
        st.success(f"✅ Found: **{result.get('title', result['query'])}**")
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
            st.markdown("### 🔄 Alternative Parts")
            
            alt_df = pd.DataFrame([{
                'Manufacturer': p['manufacturer'],
                'Part Number': p['part_number'],
                'Price (EUR)': f"€{p['price_eur']}" if p['price_eur'] else '-',
            } for p in result['products'][:15]])
            
            st.dataframe(alt_df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # Save form
            st.markdown("### 💾 Save to Google Sheets")
            
            if not sheets_service or not spreadsheet_id:
                st.warning("⚠️ Google Sheets not connected. Go to Settings tab.")
            else:
                with st.form(key="save_form"):
                    # Default selection
                    options = [f"{p['manufacturer']} - {p['part_number']}" for p in result['products'][:15]]
                    selected_option = st.selectbox("Select Default Part ⭐", options, index=0)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        brand = st.selectbox("Car Brand", BRANDS)
                        category = st.selectbox("Category", list(CATEGORIES.keys()))
                        sub_cat_options = CATEGORIES[category]
                        sub_category = st.selectbox("Sub-Category", sub_cat_options)
                        location = st.text_input("Storage Location", placeholder="e.g., Shelf A1")
                    
                    with col2:
                        qty = st.number_input("Quantity in Stock", min_value=0, value=0)
                        min_stock = st.number_input("Min Stock Level", min_value=0, value=2)
                        max_stock = st.number_input("Max Stock Level", min_value=0, value=10)
                        price_myr = st.number_input("Your Price (MYR)", min_value=0.0, value=0.0, step=1.0)
                        supplier = st.text_input("Supplier", placeholder="e.g., AutoParts MY")
                    
                    save_btn = st.form_submit_button("💾 Save to Google Sheets", type="primary", use_container_width=True)
                    
                    if save_btn:
                        selected_default = selected_option.split(" - ")[1] if " - " in selected_option else result['products'][0]['part_number']
                        
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
                        
                        part_id = save_to_google_sheets(
                            sheets_service,
                            spreadsheet_id,
                            result,
                            result['products'][:15],
                            inventory_info,
                            selected_default
                        )
                        
                        st.session_state.save_success = {
                            'part_id': part_id,
                            'oe_number': result['query'],
                            'default_pn': selected_default,
                            'alt_count': len(result['products'][:15])
                        }
                        st.session_state.search_result = None
                        st.balloons()
                        st.rerun()
        
        # Clear button
        if st.button("🔄 Clear & Search Again"):
            st.session_state.search_result = None
            st.session_state.save_success = None
            st.rerun()

# TAB 2: Database View
with tab2:
    st.markdown("### 📦 Parts Database")
    
    if not sheets_service or not spreadsheet_id:
        st.warning("⚠️ Google Sheets not connected.")
    else:
        if st.button("🔄 Refresh Data", key="refresh_db"):
            st.cache_resource.clear()
            st.rerun()
        
        # Parts Master
        st.markdown("#### Parts Master")
        try:
            df = read_sheet_as_df(sheets_service, spreadsheet_id, 'Parts_Master')
            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No parts in database yet.")
        except Exception as e:
            st.error(f"Error loading Parts Master: {e}")
        
        # Alternatives
        st.markdown("#### Alternatives / Cross-References")
        try:
            df = read_sheet_as_df(sheets_service, spreadsheet_id, 'Alternatives')
            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No alternatives yet.")
        except Exception as e:
            st.error(f"Error loading Alternatives: {e}")

# TAB 3: Inventory
with tab3:
    st.markdown("### 📊 Inventory Status")
    
    if not sheets_service or not spreadsheet_id:
        st.warning("⚠️ Google Sheets not connected.")
    else:
        if st.button("🔄 Refresh Inventory", key="refresh_inv"):
            st.cache_resource.clear()
            st.rerun()
        
        try:
            df = read_sheet_as_df(sheets_service, spreadsheet_id, 'Inventory')
            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Reorder alerts
                if 'Reorder_Needed' in df.columns:
                    reorder_items = df[df['Reorder_Needed'] == 'Yes']
                    if not reorder_items.empty:
                        st.markdown("---")
                        st.warning(f"⚠️ **{len(reorder_items)} items need reordering!**")
                        for _, item in reorder_items.iterrows():
                            st.markdown(f"- **{item.get('Default_PN', 'N/A')}** ({item.get('Category', 'N/A')}) - Stock: {item.get('Qty_In_Stock', 0)}, Min: {item.get('Min_Stock_Level', 0)}")
            else:
                st.info("No inventory data yet.")
        except Exception as e:
            st.error(f"Error loading Inventory: {e}")

# TAB 4: Vehicle Lookup
with tab4:
    st.markdown("### 🚗 Find Parts by Vehicle")
    
    if not sheets_service or not spreadsheet_id:
        st.warning("⚠️ Google Sheets not connected.")
    else:
        with st.form(key="vehicle_lookup_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                lookup_brand = st.selectbox("Car Brand", ["All"] + BRANDS)
            with col2:
                lookup_model = st.text_input("Model (optional)", placeholder="e.g., 3 Series")
            with col3:
                st.write("")
                st.write("")
                lookup_btn = st.form_submit_button("🔍 Find Parts", type="primary", use_container_width=True)
        
        if lookup_btn:
            try:
                veh_df = read_sheet_as_df(sheets_service, spreadsheet_id, 'Vehicles')
                inv_df = read_sheet_as_df(sheets_service, spreadsheet_id, 'Inventory')
                
                if not veh_df.empty:
                    # Filter
                    filtered = veh_df.copy()
                    if lookup_brand != "All" and 'Car_Brand' in filtered.columns:
                        filtered = filtered[filtered['Car_Brand'] == lookup_brand]
                    if lookup_model and 'Model' in filtered.columns:
                        filtered = filtered[filtered['Model'].str.contains(lookup_model, case=False, na=False)]
                    
                    if not filtered.empty:
                        st.success(f"✅ Found {len(filtered)} matching entries")
                        
                        # Merge with inventory
                        if not inv_df.empty and 'Part_ID' in filtered.columns and 'Part_ID' in inv_df.columns:
                            merged = filtered.merge(inv_df[['Part_ID', 'Default_PN', 'Category', 'Qty_In_Stock', 'Location']], on='Part_ID', how='left')
                            merged = merged.drop_duplicates(subset=['Part_ID'])
                            st.dataframe(merged, use_container_width=True, hide_index=True)
                        else:
                            st.dataframe(filtered, use_container_width=True, hide_index=True)
                    else:
                        st.info("No parts found for this vehicle.")
                else:
                    st.info("No vehicle data in database yet.")
            except Exception as e:
                st.error(f"Error: {e}")

# TAB 5: Settings
with tab5:
    st.markdown("### ⚙️ Settings")
    
    st.markdown("#### Connection Status")
    if sheets_service and spreadsheet_id:
        st.success("✅ Connected to Google Sheets!")
        st.code(f"Spreadsheet ID: {spreadsheet_id}")
    else:
        st.error("❌ Not connected")
    
    st.markdown("---")
    st.markdown("#### Test Connection")
    if st.button("🔄 Test Connection"):
        if sheets_service and spreadsheet_id:
            try:
                df = read_sheet_as_df(sheets_service, spreadsheet_id, 'Parts_Master')
                st.success(f"✅ Connection successful! Found {len(df)} parts.")
            except Exception as e:
                st.error(f"❌ Error: {e}")
        else:
            st.error("❌ Not configured")

# Footer
st.markdown("---")
st.markdown("<p style='text-align:center;color:#666;'>© 2025 Conti Motors • Seremban</p>", unsafe_allow_html=True)
