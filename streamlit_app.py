"""
🔧 Conti Motors Parts Lookup - Streamlit Version
================================================
Easy to deploy on Streamlit Cloud (free!)

HOW TO USE:
1. Go to streamlit.io/cloud
2. Connect your GitHub
3. Upload this file
4. Deploy!

OR run locally:
    pip install streamlit requests beautifulsoup4 lxml
    streamlit run streamlit_app.py
================================================
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
    .product-card {
        background: #1e1e2e;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #ff6b35;
        margin-bottom: 0.5rem;
    }
    .oe-tag {
        background: #ff6b35;
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 5px;
        margin: 0.2rem;
        display: inline-block;
    }
    .spec-box {
        background: #252540;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
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
        details = {
            'specifications': {},
            'oe_numbers': [],
            'cross_references': [],
            'fit_vehicles': []
        }
        
        # Specifications
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if label and value and len(label) < 40 and len(value) < 100:
                        skip = ['action', 'price', 'availability', 'check', 'details']
                        if not any(x in label.lower() for x in skip):
                            details['specifications'][label] = value
        
        # OE Numbers
        for link in soup.find_all('a', href=re.compile(r'^/oe/')):
            oe = link.get_text(strip=True)
            if oe and len(oe) > 3 and oe not in details['oe_numbers']:
                details['oe_numbers'].append(oe)
        
        # Fit Vehicles
        for link in soup.find_all('a', href=re.compile(r'/t/vehicles/')):
            text = link.get_text(strip=True)
            if text and len(text) > 3 and text not in details['fit_vehicles']:
                details['fit_vehicles'].append(text)
        
        return details
    except:
        return None

def search_spareto(oe_number):
    """Search Spareto by OE number"""
    session = get_session()
    clean_oe = re.sub(r'[\s\-]', '', oe_number)
    url = f"https://spareto.com/oe/{clean_oe}"
    
    try:
        response = session.get(url, timeout=20)
        if response.status_code == 404:
            return {'error': f'OE number "{oe_number}" not found'}
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        result = {
            'query': oe_number,
            'url': url,
            'products': [],
            'oe_numbers': [],
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
        
        # Get details from first product
        if result['products']:
            details = get_product_details(session, result['products'][0]['URL'])
            if details:
                result['specifications'] = details['specifications']
                result['oe_numbers'] = details['oe_numbers']
                result['fit_vehicles'] = details['fit_vehicles']
        
        # Fallback OE numbers from main page
        if not result['oe_numbers']:
            for link in soup.find_all('a', href=re.compile(r'^/oe/')):
                oe = link.get_text(strip=True)
                if oe and len(oe) > 3 and oe not in result['oe_numbers']:
                    result['oe_numbers'].append(oe)
        
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
st.markdown("**Quick Examples:** ", unsafe_allow_html=True)
example_cols = st.columns(4)
examples = ['31316851335', '11427566327', '04465-47060', '5K0698451A']
for i, ex in enumerate(examples):
    with example_cols[i]:
        if st.button(ex, key=f"ex_{i}"):
            oe_input = ex
            search_btn = True

# Search
if search_btn and oe_input:
    with st.spinner(f'Searching Spareto.com for "{oe_input}"...'):
        result = search_spareto(oe_input)
    
    if 'error' in result:
        st.error(f"⚠️ {result['error']}")
    else:
        # Title
        if result.get('main_title'):
            st.success(f"**{result['main_title']}**")
        
        st.markdown(f"🔗 [View on Spareto.com]({result['url']})")
        
        # Tabs for different sections
        tab1, tab2, tab3, tab4 = st.tabs(["🔧 Products", "📐 Specs", "📋 OE Numbers", "🚗 Vehicles"])
        
        # Tab 1: Products
        with tab1:
            if result['products']:
                st.markdown(f"**Found {len(result['products'])} replacement parts:**")
                df = pd.DataFrame(result['products'])
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Download button
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
                st.markdown("**Click any OE number to search:**")
                # Display as clickable buttons
                oe_cols = st.columns(5)
                for i, oe in enumerate(result['oe_numbers'][:20]):
                    with oe_cols[i % 5]:
                        st.code(oe)
            else:
                st.info("No OE numbers found")
        
        # Tab 4: Fit Vehicles
        with tab4:
            if result['fit_vehicles']:
                for vehicle in result['fit_vehicles'][:20]:
                    st.markdown(f"• {vehicle}")
            else:
                st.info("No vehicle data found")
        
        # Full download
        st.markdown("---")
        
        # Create full export
        full_data = {
            'Query': [oe_input],
            'Title': [result.get('main_title', '')],
            'URL': [result.get('url', '')],
            'Products Count': [len(result.get('products', []))],
            'OE Numbers': [', '.join(result.get('oe_numbers', []))],
            'Vehicles': [', '.join(result.get('fit_vehicles', []))]
        }
        
        # Add specs
        for k, v in result.get('specifications', {}).items():
            full_data[f'Spec: {k}'] = [v]
        
        full_df = pd.DataFrame(full_data)
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
    "<p style='text-align: center; color: #666;'>© 2025 Conti Motors • Seremban, Malaysia</p>",
    unsafe_allow_html=True
)
