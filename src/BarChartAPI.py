## ###################################################################################################################
##  Program :   BarChart API
##  Author  :   Sean Burner
##  Detail  :   Class that connects to Barchart.com via API
##  Install :   
##  Example :
##              python3 
##              python3 
##  Notes   :   https://docs.python.org/3/tutorial/classes.html
## #############################################################################
import re
import sys
import inspect
import requests
import numpy    as np
import pandas   as pd


class BarChartAPI:
    def __init__(self, symbol : str) -> None :
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.barchart.com/",
        }
        self.symbol             = symbol.strip().upper()
        self._initialized       = False        
        self.asset_path         = "indices"
        self.formatted_symbol   = self.symbol
        
        if symbol != "" and symbol != None :            
            self.Symbol( symbol =symbol)

        
    def Symbol( self, symbol : str ) -> None :
        """
            Dedicated function to setting the symbol
            PARAMETERS  :
                            symbol  [str ] - symbol provided by user that might need cleaning
            RETURNS     :
                            None
        """        
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

            
    def _initialize_session(self ) -> None :
        """
            Initialize the BarChart.com sesstion
            PARAMETERS :
                            Nothing
            RETURNS    :
                            Nothing 
        """
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

    def SpotPrice(self) -> float|None   :
        """
            Retrieves the SPOT PRICE for the provided symbol
            PARAMETERS :
                            None 
            RETURNS    :
                            None 
        """
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
                val = "".join( re.findall(r'\d+.?\d{2}', val) )                                
                if isinstance(val, dict):
                    return float(val.get('raw', 0).replace(",",''))
                return float(val.replace(",",''))
        except Exception as e:
            print(f"DEBUG: Spot Fetch Failed: {e}")
            
        return None 
    
    def MarketData(self):
        """
            Get the market data for the previously provided symbol
            PARAMETERS  :
            RETURNS     :
        """
        self._initialize_session()
        processed_list = []
        
        # 1. Properly define the plural list first
        if self.is_future:
            root            = re.match(r'^([A-Z]{2})', self.symbol).group(1)
            query_symbols   = [root, self.symbol]
            print(f"DEBUG: Future symbols are : { query_symbols} ")
        else:
            query_symbols   = [self.formatted_symbol.replace('$', '')]

        # 2. Iterate through the plural list
        for query_symbol in query_symbols:
            # Move path logic INSIDE the loop so query_symbol exists
            if self.is_future or any(x in query_symbol for x in ['ES', 'NQ', 'YM']):
                current_path    = "futures"
                ref_symbol      = re.match(r'^([A-Z]+)', query_symbol).group(1) 
            else:
                current_path    = "indices" if "SPX" in query_symbol else "stocks"
                ref_symbol      = query_symbol

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


if __name__ == "__main__":
    
    barchart = BarChartAPI("SPX")
    
    print(f"[DEBUG]  Spot Price : {barchart.SpotPrice()} " )
    print(f"[DEBUG]  Market Data : { barchart.MarketData() } " ) 
