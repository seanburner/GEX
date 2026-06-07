## ###################################################################################################################
##  Program :   Calculations
##  Author  :   Sean Burner
##  Detail  :   Class containing stock/gex calculations 
##  Install :   
##  Example :
##              python3 
##              python3 
##  Notes   :   https://docs.python.org/3/tutorial/classes.html
## #############################################################################
import sys
import inspect
import requests
import numpy    as np
import pandas   as pd


class Calculations:
    def __init__(self)-> None :
        pass 

    def DataCleaning( self, df:DataFrame) -> DataFrame:
        """
            Standard Data cleaning steps for better performance and accuracy
            PARAMETERS:
                        df  [DataFrame] - dataframe omarkdet data                        
            RETURNS   :
                        dataframe - cleaned dataframe 
        """
        try:
            print(f"[ * ] Cleaning DataFrame : {df.iloc[0]['source']}   ")
            df['strikeprice']   = pd.to_numeric(df['strikeprice'], errors='coerce')
            df['gex']           = pd.to_numeric(df['gex'], errors='coerce').fillna(0)
            df['liquidity']     = pd.to_numeric(df['liquidity'], errors='coerce').fillna(0)
            df                  = df.dropna(subset=['strikeprice'])
        except:
            print("\t\t|EXCEPTION: Calculations::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
        return df

    def FuturesStrikePrice( self, symbol : str, data: DataFrame, spot : float  ) -> (DataFrame,bool):
        """
            Check if the asset is a Futures, then readjust the strikeprice
            PARAMETERS  :
                            df     [DataFrame ]  - market data of asset
                            spot   [ float]      - spot price of asset
                            symbol [str]         - asset symbol  
            RETURNS     :
                            DataFrame
                            is_future [ bool]
        """
        max_s       = 0
        is_future   = False
        
        try:
            max_s       = data['strikeprice'].max()
            is_future   = False
            if max_s < (spot * 0.1) or "ES" in symbol.upper():
                is_future           = True
                data['strikeprice'] = data['strikeprice'] * 100
                if data['strikeprice'].max() < (spot * 0.1):
                    data['strikeprice'] = data['strikeprice'] * 10 
        except:
            print("\t\t|EXCEPTION: Calculations::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
        return data,is_future

    def ExpectedHighLow( self, spot : float) -> (float, float, float):
        """
            Calculate the Expected High and Low of the day
            PARAMETERS  :
                            spot [ float]      - spot price of asset 
            RETURNS     :
                            eh/el/em_dist (float/float/float )
        """
        eh              = 0.00
        el              = 0.00
        vol_constant    = 0.20 
        
        try:            
            em_dist         = spot * (vol_constant / (252**0.5)) 
            eh, el          = spot + em_dist, spot - em_dist
        except:
            print("\t\t|EXCEPTION: Calculations::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )

        return eh,el,em_dist

    def ZG_Strike( self, spot : float, df : DataFrame  , eh : float, el : float ) -> float :
        """
            Calculate the ZG_Strike value with validity checks
            PARAMETERS   :
                            spot      [ float ]      - spot price
                            df        [ DataFrame ]  - processed market data 
            RETURNS      :
                            float - ZG_Strike value
        """
        values      = None
        zg_strike   = spot
        found_flip  = False 
        
        try:            
            em_mask = (df['strikeprice'] >= el) & (df['strikeprice'] <= eh)
            df_active = df[em_mask].copy()
            if df_active.empty: df_active = df.copy()

            net_gex     = df_active.groupby('strikeprice')['gex'].sum().sort_index()
            if not net_gex.empty:
                strikes     = net_gex.index.values
                values      = net_gex.values
                found_flip  = False
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
        except: 
            print("\t\t|EXCEPTION: Calculations::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
                
        return zg_strike 


    def WallsData( self, df:DataFrame, spot:float )-> (DataFrame, DataFrame):
        """
            Pulls out the Call and Put walls into their own dataframes
            PARAMETERS  :
                            df   [ DataFrame] - processed market data
                            spot [ float]     - spot price 
            RETURNS     :
                            (DataFrame, DataFrame) - separated Call and Put wall data 
        """
        cw_data  = None
        pw_data  = None

        try:
            df_walls = df.groupby(['strikeprice', 'side']).agg({'liquidity': 'sum', 'gex': 'sum'}).reset_index()
            mask_c = (df_walls['side'].str.contains('c', case=False)) & (df_walls['strikeprice'] >= spot) & (df_walls['strikeprice'] <= spot * 1.07)
            mask_p = (df_walls['side'].str.contains('p', case=False)) & (df_walls['strikeprice'] <= spot) & (df_walls['strikeprice'] >= spot * 0.93)

            cw_data = df_walls[mask_c].nlargest(5, 'liquidity')
            pw_data = df_walls[mask_p].nlargest(5, 'liquidity')
        except: 
            print("\t\t|EXCEPTION: Calculations::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )

        return   cw_data, pw_data 

    def VolatilityHighLow( self, zg_strike : float, spot: float, em_dist :float) -> (float,float):
        """
            Calculate the Volatility High/Low based on ZG_Strike
            PARAMETERS  :
                            zg_strike  [ float ]  - zg_strike value
                            spot       [ float ]  - assets spot price 
                            em_dist    [ float ]  - expected move distribution 
            RETURNS     :
                            ( vh:float, vl:float )
        """
        vh, vl = 0, 0
        
        try:
            vh = max(zg_strike, spot) + (em_dist * 0.25)
            vl = min(zg_strike, spot) - (em_dist * 0.25)
        except:
            print("\t\t|EXCEPTION: Calculations::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
        return vh,vl 
                
            
    def Greeks_And_Gex(self, df : Dataframe , spot : float) -> Dataframe:
        """
            Contained business logic for calculating the Greeks and GEX info
            PARAMETERS  :
                            df   [Dataframe] - dataframe containing market data
                            spot [ float ]   - current price of symbol 
            RETURNS     :
                            None 
        """
        print(f"[ * ] Calculating Greeks and GEX : {df.iloc[0]['source']}   ")
        if df.empty: 
            return df
        try:
            
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
        except:
            print("\t\t|EXCEPTION: Calculations::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
                
        return df

if __name__ == "__main__":
    spot = 7418.3
    data = [
                {'strikeprice':7400.0,  'liquidity':3363.0, 'side':'calls'},
                {'strikeprice':7425.0,  'liquidity':894.0, 'side':'calls'},
                {'strikeprice':7375.0,  'liquidity':529.0, 'side':'calls'},
                {'strikeprice':7450.0,  'liquidity':505.0, 'side':'calls'},
                {'strikeprice':7350.0,  'liquidity':1659.0, 'side':'calls'},
                {'strikeprice':6480.0,  'liquidity':2.0, 'side':'puts'},
                {'strikeprice':6475.0,  'liquidity':5.0, 'side':'puts'},
                {'strikeprice':6470.0,  'liquidity':12.0, 'side':'puts'},
                {'strikeprice':8350.0,  'liquidity':11.0, 'side':'puts'},
                {'strikeprice':6465.0,  'liquidity':1.0, 'side':'puts'}
              ]
    
    calc = Calculations()
    print(f"[DEBUG] Calculations on spot : {spot } \n\t\t { calc.Greeks_And_Gex( df = pd.DataFrame( data ) , spot=spot) } " )
