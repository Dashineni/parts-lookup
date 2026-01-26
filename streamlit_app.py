"""
🔧 Conti Motors Parts Lookup - Streamlit Version V3
===================================================
IMPROVED: Now tries multiple search formats automatically!
Type any format - with/without spaces - it will find results!
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    return session


def generate_search_variations(query):
    """Generate multiple search variations from user input"""
    variations = []
    
    # Clean input
    original = query.strip()
    
    # 1. Original as-is
    variations.append(original)
    
    # 2. Remove ALL spaces and special characters
    no_spaces = re.sub(r'[\s\-\.\/]', '', original)
    if no_spaces not in variations:
        variations.append(no_spaces)
    
    # 3. Only alphanumeric
    alphanumeric = re.sub(r'[^a-zA-Z0-9]', '', original)
    if alphanumeric not in variations:
        variations.append(alphanumeric)
    
    # 4. Uppercase version
    upper = no_spaces.upper()
    if upper not in variations:
        variations.append(upper)
    
    # 5. Lowercase version
    lower = no_spaces.lower()
    if lower not in variations:
        variations.append(lower)
    
    # 6. With common OE number patterns (add spaces every 2-3 digits for BMW style)
    if len(no_spaces) >= 8 and no_spaces.isdigit():
        # BMW style: XX XX X XXX XXX
        spaced = f"{no_spaces[:2]} {no_spaces[2:4]} {no_spaces[4:5]} {no_spaces[5:8]} {no_spaces[8:]}"
        if spaced.strip() not in variations:
            variations.append(spaced.strip())
    
    # 7. Toyota style with dash: XXXXX-XXXXX
    if len(no_spaces) >= 10 and '-' not in original:
        dashed = f"{no_spaces[:5]}-{no_spaces[5:]}"
        if dashed not in variations:
            variations.append(dashed)
    
    return variations


def try_search_spareto(session, query):
    """Try to search Spareto with a specific query"""
    clean_query = re.sub(r'[\s\-]', '', query)
    url = f"https://spareto.com/oe/{clean_query}"
    
    try:
        response = session.get(url, timeout=15)
        
        # Check if we got a valid result (not 404, not empty)
        if response.status_code == 404:
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Check if page has actual product content
        products = soup.find_all('a', href=re.compile(r'^/products/[^/]+/[^/]+$'))
        h1 = soup.find('h1')
        
        if products or (h1 and 'not found' not in h1.get_text().lower()):
            return {'url': url, 'soup': soup, 'response': response, 'query_used': query}
        
        return None
    except:
        return None


def get_product_details(session, product_url):
    """Fetch detailed info from a product page"""
    try:
        response = session.get(product_url, timeout=25)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
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
        all_oe = []
        for link in soup.find_all('a', href=re.compile(r'^/oe/')):
            oe = link.get_text(strip=True)
            if oe and len(oe) > 3 and oe not in all_oe:
                all_oe.append(oe)
        
        if all_oe:
            # Try to find brand from page
            page_text = response.text
            brands = ['BMW', 'Toyota', 'Honda', 'VW', 'Volkswagen', 'Audi', 'Mercedes', 
                     'Nissan', 'Mazda', 'Hyundai', 'Kia', 'Ford', 'Volvo', 'Porsche', 'Mini']
            found_brand = 'OE'
            for brand in brands:
                if brand in page_text:
                    found_brand = brand
                    break
            details['oe_numbers'][found_brand] = all_oe[:20]
        
        # === CROSS-REFERENCE NUMBERS (from product links) ===
        product_links = soup.find_all('a', href=re.compile(r'^/products/'))
        refs_by_brand = {}
        for link in product_links:
            href = link.get('href', '')
            parts = href.split('/')
            if len(parts) >= 4:
                brand = parts[2].replace('-', ' ').title()
                part_num = parts[3].upper()
                if len(part_num) > 2 and len(part_num) < 30:
                    if brand not in refs_by_brand:
                        refs_by_brand[brand] = []
                    if part_num not in refs_by_brand[brand]:
                        refs_by_brand[brand].append(part_num)
        
        details['cross_references'] = refs_by_brand
        
        # === FIT VEHICLES ===
        for link in soup.find_all('a', href=re.compile(r'/t/vehicles/')):
            text = link.get_text(strip=True)
            if text and len(text) > 3:
                details['fit_vehicles'].append({
                    'model': text, 'years': '', 'kw': '', 'hp': '', 'ccm': ''
                })
        
        return details
    except Exception as e:
        return None


def search_spareto(user_query):
    """Search Spareto by trying multiple query formats"""
    session = get_session()
    
    # Generate variations of the search query
    variations = generate_search_variations(user_query)
    
    # Try each variation until one works
    result_data = None
    tried_queries = []
    
    for query in variations:
        if not query:
            continue
        tried_queries.append(query)
        result_data = try_search_spareto(session, query)
        if result_data:
            break
    
    if not result_data:
        return {
            'error': f'No results found for "{user_query}". Tried formats: {", ".join(tried_queries[:5])}',
            'tried_queries': tried_queries
        }
    
    # Parse the successful result
    soup = result_data['soup']
    url = result_data['url']
    query_used = result_data['query_used']
    
    result = {
        'query': user_query,
        'query_used': query_used,
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
    
    # Get details from first product page
    if result['products']:
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


# ============ UI ============

st.markdown('<h1 class="main-header">🔧 Conti Motors</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Parts Lookup System - Search Spareto.com</p>', unsafe_allow_html=True)

# Search box
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    oe_input = st.text_input(
        "Enter OE Number or Part Number",
        placeholder="Type any format: 31316851335 or 31 31 6 851 335",
        label_visibility="collapsed"
    )
    
    st.caption("💡 Type any format - with or without spaces - we'll find it!")
    
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
    with st.spinner(f'🔍 Searching for "{oe_input}"... (trying multiple formats)'):
        result = search_spareto(oe_input)
    
    if 'error' in result:
        st.error(f"⚠️ {result['error']}")
        if 'tried_queries' in result:
            st.info(f"Tried these formats: {', '.join(result['tried_queries'][:5])}")
    else:
        # Show which format worked
        if result.get('query_used') and result['query_used'] != oe_input:
            st.info(f"✅ Found results using format: `{result['query_used']}`")
        
        # Title
        if result.get('main_title'):
            st.success(f"**{result['main_title']}**")
        
        st.markdown(f"🔗 [View on Spareto.com]({result['url']})")
        
        # Tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🔧 Products", 
            "📐 Specs", 
            "📋 OE Numbers", 
            "🔄 Reference Numbers",
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
                    tags_html = ''.join([f'<span class="oe-tag">{num}</span>' for num in numbers])
                    st.markdown(tags_html, unsafe_allow_html=True)
                    st.markdown("")
            else:
                st.info("No OE numbers found")
        
        # Tab 4: Cross-Reference Numbers
        with tab4:
            if result['cross_references']:
                st.markdown("**Cross-Reference Numbers (aftermarket brands):**")
                for brand, numbers in result['cross_references'].items():
                    st.markdown(f"**{brand}:**")
                    tags_html = ''.join([f'<span class="ref-tag">{num}</span>' for num in numbers])
                    st.markdown(tags_html, unsafe_allow_html=True)
                    st.markdown("")
                
                # Download
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
                st.info("No cross-reference numbers found")
        
        # Tab 5: Fit Vehicles
        with tab5:
            if result['fit_vehicles']:
                vehicle_data = []
                for v in result['fit_vehicles'][:30]:
                    if isinstance(v, dict):
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
                st.info("No vehicle data found")
        
        # Download section
        st.markdown("---")
        st.markdown("### 📥 Download Full Report")
        
        full_lines = []
        full_lines.append(f"Conti Motors Parts Lookup Report")
        full_lines.append(f"Search Query: {oe_input}")
        full_lines.append(f"Format Used: {result.get('query_used', oe_input)}")
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
                full_lines.append(f"{v.get('model', '-')}")
        
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
            csv_data = {
                'Query': [oe_input],
                'Format Used': [result.get('query_used', '')],
                'Title': [result.get('main_title', '')],
                'Products Count': [len(result.get('products', []))],
                'OE Numbers': ['; '.join([f"{b}: {', '.join(n)}" for b, n in result.get('oe_numbers', {}).items()])],
                'Cross References': ['; '.join([f"{b}: {', '.join(n)}" for b, n in result.get('cross_references', {}).items()])]
            }
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
