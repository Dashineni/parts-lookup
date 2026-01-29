"""
🔧 Conti Motors Parts Database Builder
======================================
- Search parts from multiple sources (Spareto, etc.)
- View alternatives with prices
- Set default part
- Save to Google Sheets database
- Track inventory

Version: 1.0
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime
import json

# Page config
st.set_page_config(
    page_title="Conti Motors - Parts Database Builder",
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
    .default-badge {
        background: #51cf66;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
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
</style>
""", unsafe_allow_html=True)

# Initialize session state for database
if 'parts_db' not in st.session_state:
    st.session_state.parts_db = []
if 'alternatives_db' not in st.session_state:
    st.session_state.alternatives_db = []
if 'inventory_db' not in st.session_state:
    st.session_state.inventory_db = []
if 'vehicles_db' not in st.session_state:
    st.session_state.vehicles_db = []
if 'part_counter' not in st.session_state:
    st.session_state.part_counter = 1

# Categories list
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

# Session for requests
@st.cache_resource
def get_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    return session


def generate_part_id():
    """Generate unique part ID"""
    part_id = f"P{st.session_state.part_counter:04d}"
    st.session_state.part_counter += 1
    return part_id


def search_spareto(query):
    """Search Spareto for parts"""
    session = get_session()
    clean_query = re.sub(r'[\s\-]', '', query)
    url = f"https://spareto.com/oe/{clean_query}"
    
    try:
        response = session.get(url, timeout=20)
        if response.status_code == 404:
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        result = {
            'query': query,
            'url': url,
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
        
        # Products/Alternatives
        seen = set()
        for link in soup.find_all('a', href=re.compile(r'^/products/[^/]+/[^/]+$')):
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
                    'url': 'https://spareto.com' + href
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
        return None


def save_to_database(part_data, alternatives, inventory_info, selected_default):
    """Save part data to session state database"""
    part_id = generate_part_id()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Save to Parts Master
    st.session_state.parts_db.append({
        'Part_ID': part_id,
        'OE_Number': part_data['query'],
        'Brand': inventory_info['brand'],
        'Category': inventory_info['category'],
        'Sub_Category': inventory_info['sub_category'],
        'Design_Type': part_data.get('title', ''),
        'Description': part_data.get('title', ''),
        'Fits_Models': ', '.join(part_data.get('vehicles', [])[:5]),
        'Date_Added': today
    })
    
    # Save Alternatives
    for i, alt in enumerate(alternatives):
        is_default = 'Yes' if alt['part_number'] == selected_default else 'No'
        st.session_state.alternatives_db.append({
            'Part_ID': part_id,
            'OE_Number': part_data['query'],
            'Alternative_PN': alt['part_number'],
            'Manufacturer': alt['manufacturer'],
            'Is_Default': is_default,
            'Price_EUR': alt.get('price_eur', ''),
            'Price_MYR': inventory_info.get('price_myr', ''),
            'Source': 'Spareto',
            'Source_URL': alt.get('url', ''),
            'Date_Added': today
        })
    
    # Save Inventory
    default_alt = next((a for a in alternatives if a['part_number'] == selected_default), alternatives[0] if alternatives else {})
    st.session_state.inventory_db.append({
        'Part_ID': part_id,
        'OE_Number': part_data['query'],
        'Default_PN': selected_default,
        'Manufacturer': default_alt.get('manufacturer', ''),
        'Category': inventory_info['sub_category'],
        'Qty_In_Stock': inventory_info.get('qty', 0),
        'Min_Stock_Level': inventory_info.get('min_stock', 2),
        'Location': inventory_info.get('location', ''),
        'Reorder_Needed': 'Yes' if inventory_info.get('qty', 0) < inventory_info.get('min_stock', 2) else 'No',
        'Supplier': inventory_info.get('supplier', ''),
        'Date_Added': today
    })
    
    # Save Vehicles
    for vehicle in part_data.get('vehicles', []):
        st.session_state.vehicles_db.append({
            'Part_ID': part_id,
            'OE_Number': part_data['query'],
            'Car_Brand': inventory_info['brand'],
            'Model': vehicle,
            'Date_Added': today
        })
    
    return part_id


# ============ UI ============

st.markdown('<h1 class="main-header">🔧 Conti Motors</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Parts Database Builder - Search, Add & Track Inventory</p>', unsafe_allow_html=True)

# Stats row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{len(st.session_state.parts_db)}</div>
        <div class="stat-label">Parts in DB</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{len(st.session_state.alternatives_db)}</div>
        <div class="stat-label">Alternatives</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    total_stock = sum(item.get('Qty_In_Stock', 0) for item in st.session_state.inventory_db)
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{total_stock}</div>
        <div class="stat-label">Items in Stock</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    reorder_count = sum(1 for item in st.session_state.inventory_db if item.get('Reorder_Needed') == 'Yes')
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{reorder_count}</div>
        <div class="stat-label">Need Reorder</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["🔍 Search & Add Parts", "📦 View Database", "📊 Inventory", "📥 Export"])

# TAB 1: Search & Add Parts
with tab1:
    st.markdown("### Search for Parts")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            "Enter OE Number or Part Number",
            placeholder="e.g., 11427566327 or HU816X",
            label_visibility="collapsed"
        )
    with col2:
        search_btn = st.button("🔍 Search", type="primary", use_container_width=True)
    
    st.caption("💡 Type any format - with or without spaces")
    
    # Quick examples
    st.markdown("**Quick Examples:**")
    ex_cols = st.columns(6)
    examples = ['11427566327', '34116860242', '04465-47060', '5K0698451A', '1K0615301AA', 'A0004203000']
    for i, ex in enumerate(examples):
        with ex_cols[i]:
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                search_query = ex
                search_btn = True
    
    # Search results
    if search_btn and search_query:
        with st.spinner(f'🔍 Searching for "{search_query}"...'):
            result = search_spareto(search_query)
        
        if not result:
            st.error(f"⚠️ No results found for '{search_query}'")
        else:
            st.success(f"✅ Found: **{result.get('title', search_query)}**")
            st.markdown(f"🔗 [View on Spareto.com]({result['url']})")
            
            # Display OE Numbers
            if result['oe_numbers']:
                st.markdown("**📋 OE Numbers:**")
                oe_html = ''.join([f'<span class="oe-tag">{oe}</span>' for oe in result['oe_numbers'][:10]])
                st.markdown(oe_html, unsafe_allow_html=True)
            
            # Display Vehicles
            if result['vehicles']:
                st.markdown("**🚗 Fits Vehicles:**")
                v_html = ''.join([f'<span class="vehicle-tag">{v}</span>' for v in result['vehicles'][:8]])
                st.markdown(v_html, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Alternatives table with selection
            if result['products']:
                st.markdown("### 🔄 Alternative Parts - Select Default")
                
                # Create selection
                options = [f"{p['manufacturer']} - {p['part_number']} (€{p['price_eur']})" if p['price_eur'] else f"{p['manufacturer']} - {p['part_number']}" for p in result['products']]
                
                default_idx = 0
                selected_default = st.radio(
                    "Select your default part:",
                    options,
                    index=default_idx,
                    key="default_selection"
                )
                
                # Show alternatives table
                alt_df = pd.DataFrame([{
                    'Default': '⭐' if f"{p['manufacturer']} - {p['part_number']}" in selected_default else '',
                    'Manufacturer': p['manufacturer'],
                    'Part Number': p['part_number'],
                    'Price (EUR)': f"€{p['price_eur']}" if p['price_eur'] else '-'
                } for p in result['products'][:15]])
                
                st.dataframe(alt_df, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                
                # Save to database form
                st.markdown("### 💾 Save to Database")
                
                col1, col2 = st.columns(2)
                with col1:
                    brand = st.selectbox("Car Brand", BRANDS)
                    category = st.selectbox("Category", list(CATEGORIES.keys()))
                    sub_category = st.selectbox("Sub-Category", CATEGORIES[category])
                    location = st.text_input("Storage Location", placeholder="e.g., Shelf A1")
                
                with col2:
                    qty = st.number_input("Quantity in Stock", min_value=0, value=0)
                    min_stock = st.number_input("Minimum Stock Level", min_value=0, value=2)
                    price_myr = st.number_input("Your Price (MYR)", min_value=0.0, value=0.0)
                    supplier = st.text_input("Supplier Name", placeholder="e.g., AutoParts MY")
                
                if st.button("💾 Save to Database", type="primary", use_container_width=True):
                    # Get selected default part number
                    selected_pn = selected_default.split(" - ")[1].split(" (")[0] if " - " in selected_default else result['products'][0]['part_number']
                    
                    inventory_info = {
                        'brand': brand,
                        'category': category,
                        'sub_category': sub_category,
                        'location': location,
                        'qty': qty,
                        'min_stock': min_stock,
                        'price_myr': price_myr,
                        'supplier': supplier
                    }
                    
                    part_id = save_to_database(result, result['products'], inventory_info, selected_pn)
                    
                    st.markdown(f"""
                    <div class="success-box">
                        ✅ <strong>Saved successfully!</strong><br>
                        Part ID: <strong>{part_id}</strong><br>
                        OE Number: {search_query}<br>
                        Default Part: {selected_pn}<br>
                        {len(result['products'])} alternatives saved
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.balloons()

# TAB 2: View Database
with tab2:
    st.markdown("### 📦 Parts Database")
    
    if st.session_state.parts_db:
        # Parts Master
        st.markdown("#### Parts Master")
        parts_df = pd.DataFrame(st.session_state.parts_db)
        st.dataframe(parts_df, use_container_width=True, hide_index=True)
        
        # Alternatives
        st.markdown("#### Alternatives / Cross-References")
        if st.session_state.alternatives_db:
            alt_df = pd.DataFrame(st.session_state.alternatives_db)
            st.dataframe(alt_df, use_container_width=True, hide_index=True)
    else:
        st.info("No parts in database yet. Use the 'Search & Add Parts' tab to add parts.")

# TAB 3: Inventory
with tab3:
    st.markdown("### 📊 Inventory Status")
    
    if st.session_state.inventory_db:
        inv_df = pd.DataFrame(st.session_state.inventory_db)
        
        # Highlight reorder needed
        st.dataframe(inv_df, use_container_width=True, hide_index=True)
        
        # Reorder alerts
        reorder_items = [item for item in st.session_state.inventory_db if item.get('Reorder_Needed') == 'Yes']
        if reorder_items:
            st.warning(f"⚠️ {len(reorder_items)} items need reordering!")
            for item in reorder_items:
                st.markdown(f"- **{item['Default_PN']}** ({item['Category']}) - Stock: {item['Qty_In_Stock']}, Min: {item['Min_Stock_Level']}")
    else:
        st.info("No inventory data yet.")

# TAB 4: Export
with tab4:
    st.markdown("### 📥 Export Database")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Export as CSV")
        
        if st.session_state.parts_db:
            # Parts Master CSV
            parts_csv = pd.DataFrame(st.session_state.parts_db).to_csv(index=False)
            st.download_button(
                "📥 Download Parts Master",
                parts_csv,
                "conti_motors_parts_master.csv",
                "text/csv",
                use_container_width=True
            )
        
        if st.session_state.alternatives_db:
            # Alternatives CSV
            alt_csv = pd.DataFrame(st.session_state.alternatives_db).to_csv(index=False)
            st.download_button(
                "📥 Download Alternatives",
                alt_csv,
                "conti_motors_alternatives.csv",
                "text/csv",
                use_container_width=True
            )
        
        if st.session_state.inventory_db:
            # Inventory CSV
            inv_csv = pd.DataFrame(st.session_state.inventory_db).to_csv(index=False)
            st.download_button(
                "📥 Download Inventory",
                inv_csv,
                "conti_motors_inventory.csv",
                "text/csv",
                use_container_width=True
            )
    
    with col2:
        st.markdown("#### Export All (Combined)")
        
        if st.session_state.parts_db:
            # Combined export
            all_data = {
                'parts_master': st.session_state.parts_db,
                'alternatives': st.session_state.alternatives_db,
                'inventory': st.session_state.inventory_db,
                'vehicles': st.session_state.vehicles_db
            }
            
            json_str = json.dumps(all_data, indent=2)
            st.download_button(
                "📥 Download All (JSON)",
                json_str,
                "conti_motors_full_database.json",
                "application/json",
                use_container_width=True
            )
        
        st.markdown("---")
        st.markdown("#### Clear Database")
        if st.button("🗑️ Clear All Data", type="secondary"):
            st.session_state.parts_db = []
            st.session_state.alternatives_db = []
            st.session_state.inventory_db = []
            st.session_state.vehicles_db = []
            st.session_state.part_counter = 1
            st.success("Database cleared!")
            st.rerun()

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #666;'>© 2025 Conti Motors • Seremban, Malaysia</p>",
    unsafe_allow_html=True
)
