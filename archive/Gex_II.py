import requests
import pandas as pd
import numpy as np
import urllib.parse
import sys
import re


class GEXEngine:
    """
    def __init__(self, symbol):
        self.symbol = symbol.strip().upper()
        self.is_index = self.symbol in ["SPX", "XSP", "NDX", "RUT", "VIX", "ES", "NQ"] #["SPX", "XSP", "NDX", "RUT", "VIX"] ?futuresOptionsView=merged
        self.formatted_symbol = f"${self.symbol}" if self.is_index else self.symbol

        self.asset_path = "indices" if self.is_index else "stocks"
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.barchart.com/",
        }
        self._initialized = False
    """
    def __init__(self, symbol):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.barchart.com/",
        }
        self._initialized = False
        self._initialized   = False 
        self.symbol         = symbol.strip().upper()
        # ESM26 works best through the 'stocks' path with specific params
        self.is_index = self.symbol.startswith('$') or self.symbol in ["SPX", "XSP", "NDX", "RUT", "VIX"]
        self.is_future = any(self.symbol.startswith(s) for s in ["ES", "NQ", "YM", "RTY", "CL", "GC"])
        
        if self.is_index:
            self.asset_path = "indices"
            self.formatted_symbol = f"${self.symbol.replace('$', '')}"
        elif self.is_future:
            # Based on your working link, futures use the 'stocks' path for the merged view
            self.asset_path = "stocks"
            self.formatted_symbol = self.symbol
        else:
            self.asset_path = "stocks"
            self.formatted_symbol = self.symbol

        
    def _initialize_session(self):
        if self._initialized:
            return
        
        # We must hit the main quote page first to get cookies
        main_url = f"https://www.barchart.com/{self.asset_path}/quotes/{self.formatted_symbol}/overview"
        
        # If it's a future being viewed as a stock (your ESM26 case)
        if self.is_future and self.asset_path == "stocks":
            main_url = f"https://www.barchart.com/stocks/quotes/{self.symbol}/overview"

        try:
            response = self.session.get(main_url, headers=self.headers, timeout=15)
            # Fetch the XSRF-TOKEN if it exists in cookies
            if 'XSRF-TOKEN' in self.session.cookies:
                self.headers['X-XSRF-TOKEN'] = requests.utils.unquote(self.session.cookies['XSRF-TOKEN'])
            self._initialized = True
        except Exception as e:
            print(f"DEBUG: Session Init Failed: {e}")

    def fetch_spot_price(self):
        self._initialize_session()
        # API endpoint for the price data
        price_url = f"https://www.barchart.com/proxies/core-api/v1/quotes/get"
        params = {"symbols": self.formatted_symbol, "fields": "lastPrice"}
        
        try:
            resp = self.session.get(price_url, params=params, headers=self.headers, timeout=15)
            data = resp.json().get('data', [])
            if data:
                # Handle Barchart's nested 'raw' format
                val = data[0].get('lastPrice', 0)
                if isinstance(val, dict):
                    return float(val.get('raw', 0).replace(",",''))
                return float(val.replace(",",''))
        except Exception as e:
            print(f"DEBUG: Spot Fetch Failed: {e}")
        return None
    
    def fetch_market_data(self):
        self._initialize_session()
        processed_list = []
        
        # 1. Properly define the plural list first
        if self.is_future:
            root = re.match(r'^([A-Z]{2})', self.symbol).group(1)
            query_symbols = [root, self.symbol]
            print(f"DEBUG: Future symbols are : { query_symbols} ")
        else:
            query_symbols = [self.formatted_symbol.replace('$', '')]

        # 2. Iterate through the plural list
        for query_symbol in query_symbols:
            # Move path logic INSIDE the loop so query_symbol exists
            if self.is_future or any(x in query_symbol for x in ['ES', 'NQ', 'YM']):
                current_path = "futures"
                ref_symbol = re.match(r'^([A-Z]+)', query_symbol).group(1) 
            else:
                current_path = "indices" if "SPX" in query_symbol else "stocks"
                ref_symbol = query_symbol

            found_data = False
            for side in ['calls', 'puts']:
                api_url = "https://www.barchart.com/proxies/core-api/v1/options/get"
                
                # Dynamic baseSymbol: SPX needs the $ prefix for Barchart's core-api
                base_sym = f"${query_symbol}" if "SPX" in query_symbol else query_symbol
                
                params = {
                    "baseSymbol": base_sym,
                    "fields": "strikePrice,openInterest,volume,lastPrice",
                    "type": side, 
                    "order": "strikePrice,asc", 
                    "perPage": "1000",
                    "futuresOptionsView": "merged" if current_path == "futures" else ""
                }
                
                # Update Referer dynamically
                self.headers['Referer'] = f"https://www.barchart.com/{current_path}/quotes/{ref_symbol}/options"
                
                try:
                    response = self.session.get(api_url, params=params, headers=self.headers, timeout=15)
                    
                    if response.status_code != 200: 
                        continue
                    
                    data_payload = response.json().get('data', [])
                    if isinstance(data_payload, dict): 
                        data_payload = [data_payload]
                    if not data_payload: 
                        continue

                    found_data = True
                    for opt in data_payload:
                        def clean_num(val):
                            if val is None: return 0.0
                            if isinstance(val, dict):
                                val = val.get('raw', val.get('value', 0))
                            cleaned = str(val).replace(',', '') 
                            return float(cleaned) if cleaned else 0.0

                        strike = clean_num(opt.get('strikePrice'))
                        oi = clean_num(opt.get('openInterest'))
                        vol = clean_num(opt.get('volume'))
                        last = clean_num(opt.get('lastPrice'))

                        # Weighted liquidity for intraday accuracy
                        liq = oi if oi > 0 else (vol if vol > 0 else (last if last > 0 else 1.0))

                        if strike > 0:
                            processed_list.append({
                                'strikeprice': strike,
                                'liquidity': liq, 
                                'side': side
                            })
                except Exception as e:
                    print(f"DEBUG: Error during {side} fetch for {query_symbol}: {e}")

            if found_data:
                print(f"[*] Successfully pulled data using symbol: {query_symbol}")
                break
                        
        return pd.DataFrame(processed_list)
    
    """ BEST SO FAR 
    def fetch_market_data(self):
        ... (previous code blocks preserved)
    """   

    def calculate_greeks_and_gex(self, df, spot):
        if df.empty: 
            return df
        
        # List of columns we expect/want to clean
        target_cols = ['strikeprice', 'liquidity', 'volume', 'openInterest', 'lastPrice']
        
        for col in target_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                # If a core column like liquidity is missing, create it as zeros
                if col in ['strikeprice', 'liquidity']:
                    df[col] = 0.0

        # INTRADAY GEX MODEL
        # We use 'liquidity' which you've already defined as the best available 
        # metric (OI or Vol) in fetch_market_data
        df['gex'] = df['liquidity'] * (df['strikeprice'] * 0.1)
        
        # Apply side-based signs
        if 'side' in df.columns:
            df.loc[df['side'].str.contains('p', case=False, na=False), 'gex'] *= -1.0
        
        return df
    
    def build_payload(self, df, spot, symbol=""):
        try:
            if df.empty:
                return "L:0.0,ERR,ERROR,No Data,0"
            
            # 1. Clean and Numeric
            df['strikeprice'] = pd.to_numeric(df['strikeprice'], errors='coerce')
            df['gex'] = pd.to_numeric(df['gex'], errors='coerce').fillna(0)
            df['liquidity'] = pd.to_numeric(df['liquidity'], errors='coerce').fillna(0)
            df = df.dropna(subset=['strikeprice'])

            # Detect if asset is a scaled Future contract
            is_future = False
            max_s = df['strikeprice'].max()
            if max_s < (spot * 0.1) or "ES" in symbol.upper():
                is_future = True
                df['strikeprice'] = df['strikeprice'] * 100
                if df['strikeprice'].max() < (spot * 0.1):
                    df['strikeprice'] = df['strikeprice'] * 10 

            # 2. Statistical Bands (Calculated globally)
            vol_constant = 0.20 
            em_dist = spot * (vol_constant / (252**0.5)) 
            eh, el = spot + em_dist, spot - em_dist

            # 3. ZG Logic
            em_mask = (df['strikeprice'] >= el) & (df['strikeprice'] <= eh)
            df_active = df[em_mask].copy()
            if df_active.empty: df_active = df.copy()

            net_gex = df_active.groupby('strikeprice')['gex'].sum().sort_index()
            zg_strike = spot 

            if not net_gex.empty:
                strikes = net_gex.index.values
                values = net_gex.values
                found_flip = False
                for i in range(len(values) - 1):
                    if (values[i] <= 0 and values[i+1] > 0) or (values[i] >= 0 and values[i+1] < 0):
                        s1, s2 = strikes[i], strikes[i+1]
                        v1, v2 = values[i], values[i+1]
                        dist = abs(v1) + abs(v2)
                        zg_strike = (s1 * abs(v2) + s2 * abs(v1)) / dist if dist != 0 else s1
                        found_flip = True
                        break
                if not found_flip:
                    zg_strike = net_gex.abs().idxmin()

            # Target Math: VH/VL anchored directly to ZG using 25% of EM Distance
            vh = max(zg_strike, spot) + (em_dist * 0.25)
            vl = min(zg_strike, spot) - (em_dist * 0.25)

            payload = []

            # --- BRANCH TO FUTURES VS INDICES SPECIFIC FORMATTING ---
            if is_future:
                # ESM26 Target Profile: Only ZG header, followed directly by walls
                payload.append(f"L:{round(zg_strike, 1)},ZG,ZERO GAMMA,Zero Gamma~Key pivot where dealer gamma flips~Price magnet,0")
                
                df_walls = df.groupby(['strikeprice', 'side']).agg({'liquidity': 'sum', 'gex': 'sum'}).reset_index()
                mask_c = (df_walls['side'].str.contains('c', case=False)) & (df_walls['strikeprice'] >= spot) & (df_walls['strikeprice'] <= spot * 1.07)
                mask_p = (df_walls['side'].str.contains('p', case=False)) & (df_walls['strikeprice'] <= spot) & (df_walls['strikeprice'] >= spot * 0.93)

                cw_data = df_walls[mask_c].nlargest(5, 'liquidity')
                pw_data = df_walls[mask_p].nlargest(5, 'liquidity')

                walls = []
                for _, row in cw_data.iterrows():
                    s, g, liq = row['strikeprice'], row['gex'], row['liquidity']
                    dist = ((s / spot) - 1) * 100
                    g_mill = round(g / 1000000, 1)
                    line_val = g_mill if abs(g_mill) > 0 else round(liq / 100, 1)
                    walls.append(f"{round(s, 1)},CW,Call Wall,Strike: {s:.1f}~From Spot: {dist:+.2f}%~GEX: {g_mill}M,{line_val}")

                for _, row in pw_data.iterrows():
                    s, g, liq = row['strikeprice'], row['gex'], row['liquidity']
                    dist = ((s / spot) - 1) * 100
                    g_mill = round(g / 1000000, 1)
                    line_val = g_mill if abs(g_mill) > 0 else round(liq / 100, 1)
                    walls.append(f"{round(s, 1)},PW,Put Wall,Strike: {s:.1f}~From Spot: {dist:+.2f}%~GEX: {g_mill}M,{line_val}")

                walls.sort(key=lambda x: float(x.split(',')[0]), reverse=True)
                return ";".join(payload + walls)

            else:
                # SPX / SPY Target Profile: Full headers with customized structural descriptions
                payload.append(f"L:{round(zg_strike, 2)},ZG,ZERO GAMMA,Zero Gamma~Dealer gamma flips here~Price magnet")
                payload.append(f"{round(spot, 2)},MP,MAX PAIN,Max Pain~Strike with max OI~Expiry target")
                payload.append(f"{round(eh, 2)},EH,EM HIGH,Expected Move HIGH~1-sigma upper bound")
                payload.append(f"{round(el, 2)},EL,EM LOW,Expected Move LOW~1-sigma lower bound")
                payload.append(f"{round(vh, 2)},VH,VOL HIGH,Vol Band HIGH~ZG + 25% EM")
                payload.append(f"{round(vl, 2)},VL,VOL LOW,Vol Band LOW~ZG - 25% EM")

                df_walls = df.groupby(['strikeprice', 'side']).agg({'liquidity': 'sum', 'gex': 'sum'}).reset_index()
                mask_c = (df_walls['side'].str.contains('c', case=False)) & (df_walls['strikeprice'] >= spot) & (df_walls['strikeprice'] <= spot * 1.07)
                mask_p = (df_walls['side'].str.contains('p', case=False)) & (df_walls['strikeprice'] <= spot) & (df_walls['strikeprice'] >= spot * 0.93)

                cw_data = df_walls[mask_c].nlargest(5, 'liquidity')
                pw_data = df_walls[mask_p].nlargest(5, 'liquidity')
                

                walls = []
                for _, row in cw_data.iterrows():
                    s, g = row['strikeprice'], row['gex']
                    dist_points = s - spot
                    g_mill = round(g / 1000000, 1)
                    g_sign = "+" if g_mill >= 0 else ""
                    walls.append(f"{round(s, 2)},CW,Call Wall,Strike: {int(s)}~GEX: {g_sign}{g_mill}M~From spot: {dist_points:+.2f}")

                for _, row in pw_data.iterrows():
                    s, g = row['strikeprice'], row['gex']
                    dist_points = s - spot
                    g_mill = round(g / 1000000, 1)
                    g_sign = "+" if g_mill >= 0 else ""
                    walls.append(f"{round(s, 2)},PW,Put Wall,Strike: {int(s)}~GEX: {g_sign}{g_mill}M~From spot: {dist_points:+.2f}")
                walls.sort(key=lambda x: float(x.split(',')[0]), reverse=True)
                return ";".join(payload + walls)

        except Exception as e:
            return f"L:0.0,ERR,ERROR,Build Error: {str(e)}"
    """
    def build_payload(self, df, spot):
        try:
            if df.empty:
                return "L:0.0,ERR,ERROR,No Data,0"
            
            # 1. Clean and Numeric
            df['strikeprice'] = pd.to_numeric(df['strikeprice'], errors='coerce')
            df['gex'] = pd.to_numeric(df['gex'], errors='coerce').fillna(0)
            df['liquidity'] = pd.to_numeric(df['liquidity'], errors='coerce').fillna(0)
            df = df.dropna(subset=['strikeprice'])

            # 2. Scale Futures (ESM26 Fix)
            max_s = df['strikeprice'].max()
            if max_s < (spot * 0.1):
                df['strikeprice'] = df['strikeprice'] * 100
                if df['strikeprice'].max() < (spot * 0.1):
                    df['strikeprice'] = df['strikeprice'] * 10 

            # 3. Statistical Bands
            vol_constant = 0.20 
            em_dist = spot * (vol_constant / (252**0.5)) 
            eh, el = spot + em_dist, spot - em_dist
            vh, vl = spot + (em_dist * 0.25), spot - (em_dist * 0.25)

            # 4. ZG Logic
            em_mask = (df['strikeprice'] >= el) & (df['strikeprice'] <= eh)
            df_active = df[em_mask].copy()
            if df_active.empty: df_active = df.copy()

            net_gex = df_active.groupby('strikeprice')['gex'].sum().sort_index()
            zg_strike = spot 

            if not net_gex.empty:
                strikes = net_gex.index.values
                values = net_gex.values
                found_flip = False
                for i in range(len(values) - 1):
                    if (values[i] <= 0 and values[i+1] > 0) or (values[i] >= 0 and values[i+1] < 0):
                        s1, s2 = strikes[i], strikes[i+1]
                        v1, v2 = values[i], values[i+1]
                        dist = abs(v1) + abs(v2)
                        zg_strike = (s1 * abs(v2) + s2 * abs(v1)) / dist if dist != 0 else s1
                        found_flip = True
                        break
                if not found_flip:
                    zg_strike = net_gex.abs().idxmin()

            # 5. Build Headers (The core indicators)
            headers = [
                f"L:{round(zg_strike, 2)},ZG,ZERO GAMMA,Zero Gamma~Key pivot where dealer gamma flips~Price magnet,0",
                f"{round(spot, 2)},MP,MAX PAIN,Price Action~Current Spot Price Reference,0",
                f"{round(eh, 2)},EH,EM HIGH,Expected Move HIGH~1-sigma upper boundary,0",
                f"{round(el, 2)},EL,EM LOW,Expected Move LOW~1-sigma lower boundary,0",
                f"{round(vh, 2)},VH,VOL HIGH,Vol Band HIGH~ZG-weighted resistance,0",
                f"{round(vl, 2)},VL,VOL LOW,Vol Band LOW~ZG-weighted support,0"
            ]

            # 6. Build Walls (The liquidity magnets)
            df_walls = df.groupby(['strikeprice', 'side']).agg({'liquidity': 'sum', 'gex': 'sum'}).reset_index()
            
            mask_c = (df_walls['side'].str.contains('c', case=False)) & (df_walls['strikeprice'] >= spot) & (df_walls['strikeprice'] <= spot * 1.07)
            mask_p = (df_walls['side'].str.contains('p', case=False)) & (df_walls['strikeprice'] <= spot) & (df_walls['strikeprice'] >= spot * 0.93)

            cw_data = df_walls[mask_c].nlargest(5, 'liquidity')
            pw_data = df_walls[mask_p].nlargest(5, 'liquidity')

            walls = []
            
            # --- Call Wall Formatting ---
            for _, row in cw_data.iterrows():
                s, g, liq = row['strikeprice'], row['gex'], row['liquidity']
                dist = ((s / spot) - 1) * 100
                g_mill = round(g / 1000000, 1)
                
                # FALLBACK: If GEX is 0.0 (common in ESM26), use Liquidity/100 for line weight
                line_val = g_mill if abs(g_mill) > 0 else round(liq / 100, 1)
                
                # We use g_mill for the label text, but line_val for the numeric suffix
                walls.append(f"{round(s, 2)},CW,Call Wall,Strike: {s:.1f}~From Spot: {dist:+.2f}%~GEX: {g_mill}M,{line_val}")

            # --- Put Wall Formatting ---
            for _, row in pw_data.iterrows():
                s, g, liq = row['strikeprice'], row['gex'], row['liquidity']
                dist = ((s / spot) - 1) * 100
                g_mill = round(g / 1000000, 1)
                
                # FALLBACK: Apply the same logic for Puts
                line_val = g_mill if abs(g_mill) > 0 else round(liq / 100, 1)
                
                walls.append(f"{round(s, 2)},PW,Put Wall,Strike: {s:.1f}~From Spot: {dist:+.2f}%~GEX: {g_mill}M,{line_val}")
                
            # 7. FINAL SORT (Sort walls by price descending)
            walls.sort(key=lambda x: float(x.split(',')[0]), reverse=True)

            # Combine and Return
            return ";".join(headers + walls)

        except Exception as e:
            return f"L:0.0,ERR,ERROR,Build Error: {str(e)},0"
    """

    
if __name__ == "__main__":
    ticker = input("Enter Symbol (e.g. SPX, AAPL, ESM26): ").strip().upper()
    manual_spot = input("Manual Spot (Leave blank for Auto): ").strip()
    engine = GEXEngine(ticker)
    
    spot = float(manual_spot.replace(',', '')) if manual_spot else engine.fetch_spot_price()
    if not spot:
        print("[!] Error: No spot price found. Check symbol or connectivity.")
        sys.exit()
    
    print(f"[*] Analysis Price: {spot:,.2f}")
    raw_df = engine.fetch_market_data()
    
    if not raw_df.empty:
        df = engine.calculate_greeks_and_gex(raw_df, spot)
        print(f"[SUCCESS] {len(df)} active contracts processed.")
        
        # Debugging check for specific high-value strikes if applicable
        target_strike = 7000.0
        if not df[df['strikeprice'] == target_strike].empty:
             print(f"DEBUG: [main] Strike {target_strike} data found.")
             
        print("\n--- TRADINGVIEW PAYLOAD ---")
        print(engine.build_payload(df, spot))
    else:
        print("[!] Error: No market data retrieved.")
