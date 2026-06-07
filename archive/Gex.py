#
#   save output directly to clipboad : python3 gex_levels.py | grep "L:" | wl-copy
#
#
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
        # Trying to adjust for FUTURES
        self._initialize_session()
        processed_list = []
        
        # Determine the search attempts
        if self.is_future:
            # Attempt 1: Full contract (ESM26)
            # Attempt 2: Root symbol (ES) - often required for Barchart's options proxy
            root = re.match(r'([A-Z]+)', self.symbol).group(1)
            query_symbols = [self.symbol, root]
        else:
            query_symbols = [self.formatted_symbol]

        
        for query_symbol in query_symbols:
            found_data = False
            for side in ['calls', 'puts']:
                api_url = "https://www.barchart.com/proxies/core-api/v1/options/get"
                params = {
                    "baseSymbol": query_symbol,
                    "fields": "strikePrice,openInterest,volume,lastPrice",
                    "type": side, 
                    "order": "strikePrice,asc", 
                    "perPage": "1000",
                    "futuresOptionsView": "merged" # ADD THIS LINE
                }
                
                # Update Referer to match the specific asset
                self.headers['Referer'] = f"https://www.barchart.com/{self.asset_path}/quotes/{self.formatted_symbol}/options"
                
                try:
                    response = self.session.get(api_url, params=params, headers=self.headers, timeout=15)
                    if response.status_code != 200: continue
                    
                    data_payload = response.json().get('data', [])
                    if not data_payload: continue

                    found_data = True
                    for opt in data_payload:
                        def clean_num(val):
                            print(f"DEBUG: clean_num VAL -> {val} ")
                            if val is None: return 0.0
                            if isinstance(val, dict):
                                val = val.get('raw', val.get('value', 0))
                            # FIXED: Raw string r'' to eliminate SyntaxWarning
                            cleaned = val.replace(',', '') #re.sub(r'[^\\d.]', '', str(val))
                            print(f"DEBUG: clean_num CLEANED -> {cleaned} ")
                            return float(cleaned) if cleaned else 0.0

                        strike = clean_num(opt.get('strikePrice'))
                        oi = clean_num(opt.get('openInterest'))
                        vol = clean_num(opt.get('volume'))
                        last = clean_num(opt.get('lastPrice'))

                        # Intraday liquidity logic
                        liq = oi if oi > 0 else (vol if vol > 0 else (last if last > 0 else 1.0))

                        if strike > 0:
                            processed_list.append({
                                'strikeprice': strike,
                                'liquidity': liq, 
                                'side': side
                            })
                except Exception as e:
                    print(f"DEBUG: Error during {side} fetch: {e} ")

            if found_data:
                print(f"[*] Successfully pulled data using symbol: {query_symbol}")
                break
                        
        return pd.DataFrame(processed_list)
    
    """ BEST SO FAR 
    def fetch_market_data(self):
        self._initialize_session()
        processed_list = []
        
        # For Futures, Barchart often expects the baseSymbol to be the root or the full contract
        # If it's a future, we use the raw symbol; if not, we use the formatted version.
        query_symbol = self.symbol if self.is_future else self.formatted_symbol

        for side in ['calls', 'puts']:
            api_url = "https://www.barchart.com/proxies/core-api/v1/options/get"
            params = {
                "baseSymbol": query_symbol,
                "fields": "strikePrice,openInterest,volume,lastPrice",
                "type": side, 
                "order": "strikePrice,asc", 
                "perPage": "1000" 
            }
            
            # Change the Referer for futures to ensure the session remains valid
            self.headers['Referer'] = f"https://www.barchart.com/{self.asset_path}/quotes/{self.formatted_symbol}/options"
            
            response = self.session.get(api_url, params=params, headers=self.headers, timeout=15)
            print(f"DEBUG: Response : {response.text}")
            
            if response.status_code != 200: 
                print(f"DEBUG: Failed to fetch {side}. Status: {response.status_code}")
                continue
            
            data_payload = response.json().get('data', [])
            if not data_payload: 
                print(f"DEBUG: No data returned for {side} on symbol {query_symbol}")
                continue

            for opt in data_payload:
                def clean_num(val):
                    if val is None: return 0.0
                    if isinstance(val, dict):
                        val = val.get('raw', val.get('value', 0))
                    cleaned = re.sub(r'[^\\d.]', '', str(val)) #cleaned = re.sub(r'[^\\d.]', '', str(val))
                    return float(cleaned) if cleaned else 0.0

                strike = clean_num(opt.get('strikePrice'))
                oi = clean_num(opt.get('openInterest'))
                vol = clean_num(opt.get('volume'))
                last = clean_num(opt.get('lastPrice'))

                # 0DTE/Intraday Fallback
                liq = oi if oi > 0 else (vol if vol > 0 else (last if last > 0 else 1.0))

                if strike > 0:
                    processed_list.append({
                        'strikeprice': strike,
                        'liquidity': liq, 
                        'side': side
                    })
                        
        return pd.DataFrame(processed_list)
    """   
    """
    def fetch_market_data(self):
        self._initialize_session()
        processed_list = []
        for side in ['calls', 'puts']:
            api_url = "https://www.barchart.com/proxies/core-api/v1/options/get"
            params = {
                "baseSymbol": self.formatted_symbol,
                "fields": "strikePrice,openInterest,volume,lastPrice", # Added lastPrice as a 3rd fallback
                "type": side, "order": "strikePrice,asc", "perPage": "1000" 
            }
            response = self.session.get(api_url, params=params, headers=self.headers, timeout=15)
            if response.status_code != 200: continue
            
            data_payload = response.json().get('data', [])
            if not data_payload: continue

            # --- CRITICAL DEBUG: Print the first contract to see the raw values ---
            if side == 'calls':
                print(f"[*] Raw Sample for {side}: {data_payload[0]}")

            for opt in data_payload:
                def clean_num(val):
                    if val is None: return 0.0
                    # Handle cases where Barchart returns a dict like {'raw': 100, 'fmt': '100'}
                    if isinstance(val, dict):
                        val = val.get('raw', val.get('value', 0))
                    cleaned = re.sub(r'[^\\d.]', '', str(val))
                    return float(cleaned) if cleaned else 0.0

                strike = clean_num(opt.get('strikePrice'))
                oi = clean_num(opt.get('openInterest'))
                vol = clean_num(opt.get('volume'))
                last = clean_num(opt.get('lastPrice'))

                # 0DTE Logic: If OI and Vol are 0, try Last Price. 
                # If even that is 0, use 1.0 as a placeholder to ensure the strike isn't ignored.
                liq = oi if oi > 0 else (vol if vol > 0 else (last if last > 0 else 1.0))

                if strike > 0:
                    processed_list.append({
                        'strikeprice': strike,
                        'liquidity': liq, 
                        'side': side
                    })
                    
        return pd.DataFrame(processed_list)
    """

    def calculate_greeks_and_gex(self, df, spot):
        if df.empty: return df
        
        # 1. Standardize types
        df['side'] = df['side'].str.strip().str.lower()
        df['liquidity'] = pd.to_numeric(df['liquidity'], errors='coerce').fillna(0)
        df['strikeprice'] = pd.to_numeric(df['strikeprice'], errors='coerce').fillna(0)
        
        # 2. Calculate GEX per row
        # We DO NOT sum by strike yet. We keep calls and puts on separate rows.
        df['gex'] = df['liquidity'] * df['strikeprice'] * 1000.0
        
        # 3. Apply the sign - Positive for Calls, Negative for Puts
        df['gex'] = np.where(df['side'].str.contains('p'), df['gex'] * -1.0, df['gex'])
        
        return df


    def build_payload(self, df, spot):
        """
        Processes option data for 0DTE precision:
        - ZG: Linear Interpolation (Local-first)
        - EH/EL/VH/VL: Statistical bands via 0DTE Expected Move
        - Walls: Filtered by proximity with % offset metadata
        """
        display_divider = 10_000_000.0 
        
        # 1. Clean and Window
        df['strikeprice'] = pd.to_numeric(df['strikeprice'], errors='coerce')
        df['liquidity'] = pd.to_numeric(df['liquidity'], errors='coerce').fillna(0)
        df['gex'] = pd.to_numeric(df['gex'], errors='coerce').fillna(0)
        
        # Focus window: +/- 5% for 0DTE precision
        df_active = df[(df['strikeprice'] >= spot * 0.95) & (df['strikeprice'] <= spot * 1.05)].copy()
        net_gex = df_active.groupby('strikeprice')['gex'].sum().sort_index()

        # 2. Linear Interpolated Zero Gamma (Local)
        zg_strike = spot
        if not net_gex.empty:
            strikes_below = net_gex.index[net_gex.index <= spot]
            strikes_above = net_gex.index[net_gex.index > spot]
            if not strikes_below.empty and not strikes_above.empty:
                s1, s2 = strikes_below[-1], strikes_above[0]
                v1, v2 = net_gex[s1], net_gex[s2]
                if v1 * v2 <= 0:
                    dist = abs(v1) + abs(v2)
                    zg_strike = (s1 * abs(v2) + s2 * abs(v1)) / dist if dist != 0 else s1
                else:
                    zg_strike = net_gex.abs().idxmin()

        # 3. 0DTE Statistical Bands (Expected Move)
        # Using an implied 0DTE vol constant (approx 18-22% annualized for SPX)
        # EM = Spot * (Vol / sqrt(252))
        vol_constant = 0.20 
        expected_move = spot * (vol_constant / np.sqrt(252))
        
        eh = spot + expected_move
        el = spot - expected_move
        vh = zg_strike + (expected_move * 0.25)
        vl = zg_strike - (expected_move * 0.25)

        # 4. Max Pain (Simplified for Intraday)
        max_pain = spot # Often mirrors spot in 0DTE
        try:
            strikes = df_active['strikeprice'].unique()
            c = df_active[df_active['side'].str.contains('c')]
            p = df_active[df_active['side'].str.contains('p')]
            s_vec = strikes[:, None]
            payouts = np.sum(c['liquidity'].values * np.maximum(s_vec - c['strikeprice'].values, 0), axis=1) + \
                      np.sum(p['liquidity'].values * np.maximum(p['strikeprice'].values - s_vec, 0), axis=1)
            max_pain = strikes[np.argmin(payouts)]
        except: pass

        # 5. Proximity-Based Walls
        # We want the highest liquidity levels that are actually near the price
        # Call Walls (Resistance)
        cw_pool = df_active[df_active['strikeprice'] >= spot].groupby('strikeprice')['liquidity'].sum()
        cw_top = cw_pool.sort_values(ascending=False).head(5)
        
        # Put Walls (Support)
        pw_pool = df_active[df_active['strikeprice'] < spot].groupby('strikeprice')['liquidity'].sum()
        pw_top = pw_pool.sort_values(ascending=False).head(5)

        # 6. Payload Assembly
        payload = []
        
        # Primary Anchors with Metadata
        payload.append(f"L:{round(zg_strike, 2)},ZG,ZERO GAMMA,Zero Gamma~Key pivot where dealer gamma flips~Price magnet,0")
        payload.append(f"{round(max_pain, 2)},MP,MAX PAIN,Max Pain~Strike with maximum open interest~Expiry target,0")
        payload.append(f"{round(eh, 2)},EH,EM HIGH,Expected Move HIGH~1-sigma upper boundary~Statistical resistance,0")
        payload.append(f"{round(el, 2)},EL,EM LOW,Expected Move LOW~1-sigma lower boundary~Statistical support,0")
        payload.append(f"{round(vh, 2)},VH,VOL HIGH,Vol Band HIGH~Volatility-based resistance~ZG + 25% EM,0")
        payload.append(f"{round(vl, 2)},VL,VOL LOW,Vol Band LOW~Volatility-based support~ZG - 25% EM,0")

        # Dynamic Walls with % offsets
        for s, liq in cw_top.items():
            diff = ((s / spot) - 1) * 100
            payload.append(f"{round(s, 2)},CW,Call Wall,Strike: {s:.2f}~From Spot: {diff:+.2f}%,0")

        for s, liq in pw_top.items():
            diff = ((s / spot) - 1) * 100
            payload.append(f"{round(s, 2)},PW,Put Wall,Strike: {s:.2f}~From Spot: {diff:+.2f}%,0")

        return ";".join(payload)

    """ RESTORED - ALMOST PERFECT
    def build_payload(self, df, spot):        
        #Processes mirrored option data to extract logical 0DTE levels.
        #- Zero Gamma: Calculated via Linear Interpolation of Net GEX.
        #- Walls: Separated by proximity and location relative to spot.
        
        display_divider = 10_000_000.0 
        
        # 1. DATA CLEANING & TYPE CASTING
        df['strikeprice'] = pd.to_numeric(df['strikeprice'], errors='coerce')
        df['liquidity'] = pd.to_numeric(df['liquidity'], errors='coerce').fillna(0)
        df['gex'] = pd.to_numeric(df['gex'], errors='coerce').fillna(0)

        # 2. WINDOWING (Focus on 0DTE relevance: +/- 10% of spot)
        upper_bound, lower_bound = spot * 1.10, spot * 0.90
        df_active = df[(df['strikeprice'] >= lower_bound) & (df['strikeprice'] <= upper_bound)].copy()

        # 3. NET GEX CALCULATION (Fixes Mirrored Data)
        # Summing GEX by strike cancels out the 'mirrored' positive/negative values 
        # and leaves us with the true Net Dealer Exposure at each level.
        net_gex = df_active.groupby('strikeprice')['gex'].sum().sort_index()

        # 4. ACCURATE GEX ZERO (LOCAL CROSSOVER)
        # We only want the flip closest to the current spot price
        zg_strike = spot
        
        if not net_gex.empty:
            # Sort by distance to spot so we evaluate the closest strikes first
            # This prevents deep OTM "mirrored" errors from pulling the ZG away
            idx_near_spot = (net_gex.index.to_series() - spot).abs().sort_values().index
            
            # We look for the crossover specifically in the strikes flanking the spot
            # Find the strike immediately below and immediately above spot
            strikes_below = net_gex.index[net_gex.index <= spot]
            strikes_above = net_gex.index[net_gex.index > spot]

            if not strikes_below.empty and not strikes_above.empty:
                s1 = strikes_below[-1] # Highest strike below spot
                s2 = strikes_above[0]  # Lowest strike above spot
                v1, v2 = net_gex[s1], net_gex[s2]

                if v1 * v2 <= 0: # Local Flip exists
                    total_dist = abs(v1) + abs(v2)
                    zg_strike = (s1 * abs(v2) + s2 * abs(v1)) / total_dist if total_dist != 0 else s1
                else:
                    # If no flip right at spot, fallback to the global minimum in the 0DTE window
                    zg_strike = net_gex.abs().idxmin()

        # 5. WALL SEPARATION (Logical Resistance vs Support)
        # Call Walls = Overhead (Strikes >= Spot)
        cw_agg = df_active[df_active['strikeprice'] >= spot].groupby('strikeprice')['liquidity'].sum()
        cw_top = cw_agg.sort_values(ascending=False).head(5)

        # Put Walls = Underneath (Strikes < Spot)
        pw_agg = df_active[df_active['strikeprice'] < spot].groupby('strikeprice')['liquidity'].sum()
        pw_top = pw_agg.sort_values(ascending=False).head(5)

        # 6. PAYLOAD CONSTRUCTION
        payload = []
        
        # Primary Anchors
        print(f"DEBUG:  ZG :{round(zg_strike *10, 1)}   Spot :{ round(spot*10,1)}   % Diff : {zg_strike/spot} -> {spot/zg_strike} EVAL : {0.99995 >= (zg_strike /spot) <= 1.005}")
        if 0.99995 <= (zg_strike /spot) <= 1.005: # round(zg_strike , 1) == round(spot , 1):
            zg_strike += 0.00005  * spot  
        payload.append(f"L:{round(zg_strike, 1)},ZG,ZERO GAMMA,Zero Gamma,0")
        payload.append(f"{round(spot, 1)},MP,MAX PAIN,Max Pain,0")

        # Call Walls (Resistance)
        for s, liq in cw_top.items():
            val = round((liq * s * 1000.0) / display_divider, 1)
            payload.append(f"{round(s, 1)},CW,Call Wall,GEX: {val}M,{val}")

        # Put Walls (Support)
        for s, liq in pw_top.items():
            val = round((liq * s * 1000.0) / display_divider, 1)
            payload.append(f"{round(s, 1)},PW,Put Wall,GEX: {val}M,{val}")

        # Optional: Sort the payload by strike price so the TV labels are ordered
        # (Excluding the ZG/MP which usually sit at the top of the string)
        meta = payload[:2] # ZG and MP
        levels = payload[2:]
        levels.sort(key=lambda x: float(x.split(',')[0]))
        final_payload = ";".join(meta + levels)
        
        return final_payload
    """
    """  RESTORED 
    def build_payload(self, df, spot):
        display_divider = 10_000_000.0 
        
        # 1. Actionable Range: +/- 10% of spot
        mask = (df['strikeprice'] >= spot * 0.90) & (df['strikeprice'] <= spot * 1.10)
        df_near = df[mask].copy()
        if df_near.empty: 
            df_near = df.copy()

        # 2. SEPARATE POOLS BY SIDE COLUMN
        # We ignore the existing 'gex' column and recalculate it per side to be safe
        df_near['raw_gex'] = df_near['liquidity'] * df_near['strikeprice'] * 1000.0
        
        calls = df_near[df_near['side'].str.contains('c', case=False)].copy()
        puts = df_near[df_near['side'].str.contains('p', case=False)].copy()

        # 3. Aggregate Walls
        cw_agg = calls.groupby('strikeprice')['raw_gex'].sum().sort_values(ascending=False).head(5)
        # For puts, we use the raw GEX but keep in mind these are support levels
        pw_agg = puts.groupby('strikeprice')['raw_gex'].sum().sort_values(ascending=False).head(5)

        # 4. ZERO GAMMA (ZG) - Use the NET (Calls - Puts)
        # We need a shared index to subtract them properly
        call_net = calls.groupby('strikeprice')['raw_gex'].sum()
        put_net = puts.groupby('strikeprice')['raw_gex'].sum()
        net_gex = call_net.reindex(df_near['strikeprice'].unique(), fill_value=0) - \
                  put_net.reindex(df_near['strikeprice'].unique(), fill_value=0)
        
        zg_strike = net_gex.abs().idxmin()

        # 5. MAX PAIN
        max_pain = spot
        try:
            strikes = df_near['strikeprice'].unique()
            s_vec = strikes[:, None]
            c_payout = np.sum(calls['liquidity'].values * np.maximum(s_vec - calls['strikeprice'].values, 0), axis=1)
            p_payout = np.sum(puts['liquidity'].values * np.maximum(puts['strikeprice'].values - s_vec, 0), axis=1)
            max_pain = strikes[np.argmin(c_payout + p_payout)]
        except: pass

        payload = []
        payload.append(f"L:{round(zg_strike, 1)},ZG,ZERO GAMMA,Zero Gamma,0")
        payload.append(f"{round(max_pain, 1)},MP,MAX PAIN,Max Pain,0")

        # 6. Top 5 Call Walls
        for s, g in cw_agg.items():
            val_m = round(g / display_divider, 1)
            payload.append(f"{round(s, 1)},CW,Call Wall,GEX: {val_m}M,{val_m}")

        # 7. Top 5 Put Walls
        for s, g in pw_agg.items():
            val_m = round(g / display_divider, 1)
            payload.append(f"{round(s, 1)},PW,Put Wall,GEX: {val_m}M,{val_m}")

        return ";".join(payload)
    """

    
if __name__ == "__main__":
    ticker = input("Enter Symbol (e.g. SPX, AAPL): ").strip().upper()
    manual_spot = input("Manual Spot (Leave blank for Auto): ").strip()
    engine = GEXEngine(ticker)
    
    spot = float(manual_spot.replace(',', '')) if manual_spot else engine.fetch_spot_price()
    if not spot:
        print("[!] Error: No spot price.")
        sys.exit()
    
    print(f"[*] Analysis Price: {spot:,.2f}")
    raw_df = engine.fetch_market_data()
    
    if not raw_df.empty:
        df = engine.calculate_greeks_and_gex(raw_df, spot)
        print(f"[SUCCESS] {len(df)} active contracts processed.")
        print(f"DEBUG: [main] DF strikeprice == 7000: {df[df['strikeprice'] == 7000.0]}")
        print("\n--- TRADINGVIEW PAYLOAD ---")
        print(engine.build_payload(df, spot))
