"""
🔧 Conti Motors Parts Lookup - Streamlit Version V2
===================================================
Now includes: Products, Specs, OE Numbers, Cross-References, Fit Vehicles
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

# Page config
st.set_page_config(
    page_title="Conti Motors Parts Lookup",
    page_icon="🔧",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #ff6b35;
        text-align: center;
        margin-bottom: 0;
    }
    .sub-header {
        text-align: center;
        color: #888;
        margin-bottom: 2rem;
    }
    .ref-tag {
        background: #e8f4f8;
        border: 1px solid #4dabf7;
        color: #1971c2;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        margin: 0.3rem;
        display: inline-block;
        font-family: monospace;
        font-weight: bold;
    }
    .oe-tag {
        background: #fff3e6;
        border: 1px solid #ff6b35;
        color: #d9480f;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        margin: 0.3rem;
        display: inline-block;
        font-family: monospace;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Session for requests
@st.cache_resource
def get_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    return session

def get_product_details(session, product_url):
    """Fetch detailed info from a product page"""
    try:
        response = session.get(product_url, timeout=25)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        page_text = response.text
        
        details = {
            'specifications': {},
            'oe_numbers': {},
            'cross_references': {},
            'fit_vehicles': []
        }
        
        # === SPECIFICATIONS ===
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if label and value and len(label) < 40 and len(value) < 100:
                        skip = ['action', 'price', 'availability', 'check', 'details', 'manufacturer', 'part number']
                        if not any(x in label.lower() for x in skip):
                            details['specifications'][label] = value
        
        # === OE NUMBERS ===
        # Find OE Numbers section specifically
        oe_section_found = False
        for element in soup.find_all(['h2', 'h3', 'h4', 'div', 'section']):
            text = element.get_text(strip=True).lower()
            if 'oe number' in text or 'oe-number' in text:
                oe_section_found = True
                # Look for the parent or next sibling with OE data
                parent = element.find_parent(['div', 'section', 'table'])
                if parent:
                    # Find brand rows
                    rows = parent.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if cells:
                            first_cell = cells[0].get_text(strip=True)
                            # Check if first cell is a brand name
                            brands = ['BMW', 'Toyota', 'Honda', 'VW', 'Volkswagen', 'Audi', 'Mercedes', 'Mercedes-Benz', 
                                     'Nissan', 'Mazda', 'Hyundai', 'Kia', 'Ford', 'Opel', 'Peugeot', 'Renault', 'Volvo',
                                     'Porsche', 'Mini', 'Skoda', 'Seat', 'Fiat', 'Alfa Romeo', 'Citroen', 'Lexus']
                            if first_cell in brands:
                                brand = first_cell
                                # Get OE numbers from remaining cells or links
                                oe_links = row.find_all('a', href=re.compile(r'/oe/'))
                                if oe_links:
                                    if brand not in details['oe_numbers']:
                                        details['oe_numbers'][brand] = []
                                    for link in oe_links:
                                        oe = link.get_text(strip=True)
                                        if oe and oe not in details['oe_numbers'][brand]:
                                            details['oe_numbers'][brand].append(oe)
        
        # Fallback: Get all OE links if section not found
        if not details['oe_numbers']:
            all_oe = []
            for link in soup.find_all('a', href=re.compile(r'^/oe/')):
                oe = link.get_text(strip=True)
                if oe and len(oe) > 3 and oe not in all_oe:
                    all_oe.append(oe)
            if all_oe:
                details['oe_numbers']['OE'] = all_oe[:20]
        
        # === CROSS-REFERENCE NUMBERS ===
        # Find Cross-Reference section
        for element in soup.find_all(['h2', 'h3', 'h4', 'div', 'section']):
            text = element.get_text(strip=True).lower()
            if 'cross-reference' in text or 'cross reference' in text or 'reference number' in text:
                parent = element.find_parent(['div', 'section', 'table'])
                if parent:
                    rows = parent.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if cells:
                            first_cell = cells[0].get_text(strip=True)
                            # Check if first cell is a brand name
                            brands = ['BMW', 'Toyota', 'Honda', 'VW', 'Volkswagen', 'Audi', 'Mercedes', 'Mercedes-Benz',
                                     'Bosch', 'MANN-FILTER', 'Mann', 'Febi', 'Febi Bilstein', 'Lemforder', 'Lemförder',
                                     'TRW', 'ATE', 'Brembo', 'Textar', 'Mahle', 'Hengst', 'Filtron', 'Sachs', 'SKF',
                                     'Continental', 'Gates', 'Dayco', 'INA', 'FAG', 'LuK', 'Valeo', 'Denso', 'NGK',
                                     'Delphi', 'Moog', 'Monroe', 'KYB', 'Bilstein', 'Meyle', 'Swag', 'Topran', 'JP Group']
                            if first_cell in brands or any(b.lower() in first_cell.lower() for b in brands):
                                brand = first_cell
                                # Get reference numbers from links or text
                                ref_links = row.find_all('a')
                                if ref_links:
                                    if brand not in details['cross_references']:
                                        details['cross_references'][brand] = []
                                    for link in ref_links:
                                        ref = link.get_text(strip=True)
                                        href = link.get('href', '')
                                        # Skip OE links, we want product/reference links
                                        if ref and '/oe/' not in href and ref not in details['cross_references'][brand]:
                                            if len(ref) > 2 and len(ref) < 30:
                                                details['cross_references'][brand].append(ref)
        
        # Alternative: Extract from product links on page
        if not details['cross_references']:
            product_links = soup.find_all('a', href=re.compile(r'^/products/'))
            seen_refs = {}
            for link in product_links:
                href = link.get('href', '')
                parts = href.split('/')
                if len(parts) >= 4:
                    brand = parts[2].replace('-', ' ').title()
                    part_num = parts[3].upper()
                    if brand not in seen_refs:
                        seen_refs[brand] = []
                    if part_num not in seen_refs[brand] and len(part_num) > 2:
                        seen_refs[brand].append(part_num)
            
            # Filter to only aftermarket brands
            aftermarket = ['Febi Bilstein', 'Lemforder', 'Trw', 'Bosch', 'Mann Filter', 'Mahle', 'Meyle', 
                          'Swag', 'Topran', 'Valeo', 'Sachs', 'Ate', 'Brembo', 'Textar', 'Hengst']
            for brand, refs in seen_refs.items():
                if any(am.lower() in brand.lower() for am in aftermarket):
                    details['cross_references'][brand] = refs[:10]
        
        # === FIT VEHICLES ===
        for element in soup.find_all(['h2', 'h3', 'h4', 'div', 'section']):
            text = element.get_text(strip=True).lower()
            if 'fit vehicle' in text or 'application' in text or 'compatible' in text:
                parent = element.find_parent(['div', 'section'])
                if parent:
                    # Look for vehicle tables
                    tables = parent.find_all('table')
                    for table in tables:
                        rows = table.find_all('tr')
                        for row in rows[1:]:  # Skip header
                            cells = row.find_all('td')
                            if len(cells) >= 2:
                                vehicle = {
                                    'model': '',
                                    'years': '',
                                    'kw': '',
                                    'hp': '',
                                    'ccm': ''
                                }
                                for cell in cells:
                                    text = cell.get_text(strip=True)
                                    # Detect type of data
                                    if re.search(r'xDrive|sDrive|TDI|TSI|TFSI|[A-Z]\d{1,2}\s*\(', text):
                                        vehicle['model'] = text
                                    elif re.match(r'\d{4}[-/]\d{2}\s*-\s*\d{4}[-/]\d{2}', text):
                                        vehicle['years'] = text
                                    elif re.match(r'^\d{2,3}$', text):
                                        num = int(text)
                                        if not vehicle['kw']:
                                            vehicle['kw'] = text
                                        elif not vehicle['hp']:
                                            vehicle['hp'] = text
                                    elif re.match(r'^\d{4}$', text) and int(text) > 500:
                                        vehicle['ccm'] = text
                                
                                if vehicle['model']:
                                    details['fit_vehicles'].append(vehicle)
        
        # Fallback: Get vehicle links
        if not details['fit_vehicles']:
            for link in soup.find_all('a', href=re.compile(r'/t/vehicles/')):
                text = link.get_text(strip=True)
                if text and len(text) > 3:
                    details['fit_vehicles'].append({
                        'model': text, 'years': '', 'kw': '', 'hp': '', 'ccm': ''
                    })
        
        return details
    except Exception as e:
        st.error(f"Error fetching details: {e}")
        return None


def search_spareto(oe_number):
    """Search Spareto by OE number"""
    session = get_session()
    clean_oe = re.sub(r'[\s\-]', '', oe_number)
    url = f"https://spareto.com/oe/{clean_oe}"
    
    try:
        response = session.get(url, timeout=20)
        if response.status_code == 404:
            return {'error': f'OE number "{oe_number}" not found on Spareto.com'}
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        result = {
            'query': oe_number,
            'url': url,
            'products': [],
            'oe_numbers': {},
            'cross_references': {},
            'specifications': {},
            'fit_vehicles': [],
            'main_title': ''
        }
        
        # Title
        h1 = soup.find('h1')
        if h1:
            result['main_title'] = h1.get_text(strip=True)
        
        # Products
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
                    'Manufacturer': manufacturer,
                    'Part Number': part_number,
                    'Price (EUR)': price if price else '-',
                    'URL': 'https://spareto.com' + href
                })
        
        # Get details from first product page (has more info)
        if result['products']:
            with st.spinner('Fetching detailed specifications...'):
                details = get_product_details(session, result['products'][0]['URL'])
                if details:
                    result['specifications'] = details['specifications']
                    result['oe_numbers'] = details['oe_numbers']
                    result['cross_references'] = details['cross_references']
                    result['fit_vehicles'] = details['fit_vehicles']
        
        # Fallback: Get OE numbers from main page
        if not result['oe_numbers']:
            all_oe = []
            for link in soup.find_all('a', href=re.compile(r'^/oe/')):
                oe = link.get_text(strip=True)
                if oe and len(oe) > 3 and oe not in all_oe:
                    all_oe.append(oe)
            if all_oe:
                result['oe_numbers']['OE'] = all_oe[:20]
        
        # Fallback: Build cross-references from products list
        if not result['cross_references'] and result['products']:
            refs_by_brand = {}
            for p in result['products']:
                brand = p['Manufacturer']
                part = p['Part Number']
                if brand not in refs_by_brand:
                    refs_by_brand[brand] = []
                if part not in refs_by_brand[brand]:
                    refs_by_brand[brand].append(part)
            result['cross_references'] = refs_by_brand
        
        return result
    except Exception as e:
        return {'error': str(e)}


# ============ UI ============

st.markdown('<h1 class="main-header">🔧 Conti Motors</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Parts Lookup System - Search Spareto.com</p>', unsafe_allow_html=True)

# Search box
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    oe_input = st.text_input(
        "Enter OE Number",
        placeholder="e.g., 31316851335 or 11427566327",
        label_visibility="collapsed"
    )
    
    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_b:
        search_btn = st.button("🔍 Search Spareto", type="primary", use_container_width=True)

# Quick examples
st.markdown("---")
st.markdown("**Quick Examples:** ")
example_cols = st.columns(4)
examples = ['31316851335', '11427566327', '04465-47060', '5K0698451A']
for i, ex in enumerate(examples):
    with example_cols[i]:
        if st.button(ex, key=f"ex_{i}"):
            st.session_state['search_query'] = ex
            st.rerun()

# Check for session state search
if 'search_query' in st.session_state:
    oe_input = st.session_state['search_query']
    search_btn = True
    del st.session_state['search_query']

# Search
if search_btn and oe_input:
    with st.spinner(f'🔍 Searching Spareto.com for "{oe_input}"...'):
        result = search_spareto(oe_input)
    
    if 'error' in result:
        st.error(f"⚠️ {result['error']}")
    else:
        # Title
        if result.get('main_title'):
            st.success(f"**{result['main_title']}**")
        
        st.markdown(f"🔗 [View on Spareto.com]({result['url']})")
        
        # Tabs for different sections - NOW WITH 5 TABS!
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🔧 Products", 
            "📐 Specs", 
            "📋 OE Numbers", 
            "🔄 Reference Numbers",  # NEW TAB!
            "🚗 Vehicles"
        ])
        
        # Tab 1: Products
        with tab1:
            if result['products']:
                st.markdown(f"**Found {len(result['products'])} replacement parts:**")
                df = pd.DataFrame(result['products'])
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Download Products CSV",
                    csv,
                    f"spareto_{oe_input}_products.csv",
                    "text/csv"
                )
            else:
                st.info("No products found")
        
        # Tab 2: Specifications
        with tab2:
            if result['specifications']:
                cols = st.columns(3)
                for i, (key, value) in enumerate(result['specifications'].items()):
                    with cols[i % 3]:
                        st.metric(key, value)
            else:
                st.info("No specifications found")
        
        # Tab 3: OE Numbers
        with tab3:
            if result['oe_numbers']:
                st.markdown("**Original Equipment Numbers (from car manufacturers):**")
                for brand, numbers in result['oe_numbers'].items():
                    st.markdown(f"**{brand}:**")
                    # Display as styled tags
                    tags_html = ''.join([f'<span class="oe-tag">{num}</span>' for num in numbers])
                    st.markdown(tags_html, unsafe_allow_html=True)
                    st.markdown("")
            else:
                st.info("No OE numbers found")
        
        # Tab 4: Cross-Reference Numbers (NEW!)
        with tab4:
            if result['cross_references']:
                st.markdown("**Cross-Reference Numbers (aftermarket brands):**")
                for brand, numbers in result['cross_references'].items():
                    st.markdown(f"**{brand}:**")
                    # Display as styled tags
                    tags_html = ''.join([f'<span class="ref-tag">{num}</span>' for num in numbers])
                    st.markdown(tags_html, unsafe_allow_html=True)
                    st.markdown("")
                
                # Download cross-references
                ref_data = []
                for brand, numbers in result['cross_references'].items():
                    for num in numbers:
                        ref_data.append({'Brand': brand, 'Reference Number': num})
                if ref_data:
                    ref_df = pd.DataFrame(ref_data)
                    ref_csv = ref_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Reference Numbers CSV",
                        ref_csv,
                        f"spareto_{oe_input}_references.csv",
                        "text/csv"
                    )
            else:
                st.info("No cross-reference numbers found. Check the Products tab - the part numbers there are the reference numbers.")
        
        # Tab 5: Fit Vehicles
        with tab5:
            if result['fit_vehicles']:
                if isinstance(result['fit_vehicles'][0], dict):
                    # Table format
                    vehicle_data = []
                    for v in result['fit_vehicles'][:30]:
                        vehicle_data.append({
                            'Model': v.get('model', '-'),
                            'Years': v.get('years', '-'),
                            'KW': v.get('kw', '-'),
                            'HP': v.get('hp', '-'),
                            'CCM': v.get('ccm', '-')
                        })
                    if vehicle_data:
                        vdf = pd.DataFrame(vehicle_data)
                        st.dataframe(vdf, use_container_width=True, hide_index=True)
                else:
                    # Simple list
                    for vehicle in result['fit_vehicles'][:20]:
                        st.markdown(f"• {vehicle}")
            else:
                st.info("No vehicle data found")
        
        # Full download section
        st.markdown("---")
        st.markdown("### 📥 Download Full Report")
        
        # Create comprehensive export
        full_lines = []
        full_lines.append(f"Conti Motors Parts Lookup Report")
        full_lines.append(f"Query: {oe_input}")
        full_lines.append(f"URL: {result.get('url', '')}")
        full_lines.append(f"Title: {result.get('main_title', '')}")
        full_lines.append("")
        
        full_lines.append("=== REPLACEMENT PARTS ===")
        for p in result.get('products', []):
            full_lines.append(f"{p['Manufacturer']}, {p['Part Number']}, {p['Price (EUR)']}, {p['URL']}")
        full_lines.append("")
        
        full_lines.append("=== SPECIFICATIONS ===")
        for k, v in result.get('specifications', {}).items():
            full_lines.append(f"{k}: {v}")
        full_lines.append("")
        
        full_lines.append("=== OE NUMBERS ===")
        for brand, nums in result.get('oe_numbers', {}).items():
            full_lines.append(f"{brand}: {', '.join(nums)}")
        full_lines.append("")
        
        full_lines.append("=== CROSS-REFERENCE NUMBERS ===")
        for brand, nums in result.get('cross_references', {}).items():
            full_lines.append(f"{brand}: {', '.join(nums)}")
        full_lines.append("")
        
        full_lines.append("=== FIT VEHICLES ===")
        for v in result.get('fit_vehicles', []):
            if isinstance(v, dict):
                full_lines.append(f"{v.get('model', '-')}, {v.get('years', '-')}, {v.get('kw', '-')}kw, {v.get('hp', '-')}hp, {v.get('ccm', '-')}ccm")
            else:
                full_lines.append(str(v))
        
        full_text = '\n'.join(full_lines)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 Download Full Report (TXT)",
                full_text,
                f"spareto_{oe_input}_full_report.txt",
                "text/plain",
                use_container_width=True
            )
        with col2:
            # CSV version
            csv_data = {
                'Query': [oe_input],
                'Title': [result.get('main_title', '')],
                'Products Count': [len(result.get('products', []))],
                'OE Numbers': ['; '.join([f"{b}: {', '.join(n)}" for b, n in result.get('oe_numbers', {}).items()])],
                'Cross References': ['; '.join([f"{b}: {', '.join(n)}" for b, n in result.get('cross_references', {}).items()])],
                'Vehicles': [', '.join([v.get('model', str(v)) if isinstance(v, dict) else str(v) for v in result.get('fit_vehicles', [])])]
            }
            for k, v in result.get('specifications', {}).items():
                csv_data[f'Spec_{k}'] = [v]
            
            full_df = pd.DataFrame(csv_data)
            full_csv = full_df.to_csv(index=False)
            
            st.download_button(
                "📥 Download Full Report (CSV)",
                full_csv,
                f"spareto_{oe_input}_full_report.csv",
                "text/csv",
                use_container_width=True
            )

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #666;'>© 2025 Conti Motors • Seremban, Malaysia<br>Data from Spareto.com</p>",
    unsafe_allow_html=True
)
