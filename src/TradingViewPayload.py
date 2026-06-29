## ###################################################################################################################
##  Program :   TradingViewPayload
##  Author  :   Sean Burner
##  Detail  :   Produces the string to feed into TradingView indicator 
##  Install :   
##  Example :
##              python3 
##              python3 
##  Notes   :   https://docs.python.org/3/tutorial/classes.html
## #############################################################################
import re
import sys
import getpass
import inspect
import numpy    as np
import pandas   as pd

from pandas 		import DataFrame
from Calculations 	import Calculations

Extraneous_Levels = ['VH','VL','EH','EL']       # needs to be centralized, also in ConflueneEngine 


class TradingViewPayload:
    def __init__( self ) -> None :
        self.calc      = Calculations()
        

    def Build( self , data : DataFrame, symbol : str,  spot : float ) -> str :
        """
            Coordinates the functions to produce the string for TradingView
            PARAMETERS  :
                            data  [DataFrame ] - symbol market data
                            spot  [ float ]    - spot price for symbol stock 
            RETURNS     :
                            string - formatted string for TradingView 
        """        
        #calc        = Calculations()
        walls       = []
        payload     = ""
        is_future   = False 
        
        try:
            if data.empty:
                return "L:0.0,ERR,ERROR,No Data,0"

            # 1. Clean and Numeric
            data = self.calc.DataCleaning( df=data)
            
            # Detect if asset is a scaled Future contract            
            data, is_future   = self.calc.FuturesStrikePrice(symbol=symbol,  data=data, spot=spot)
            
            # 2. Statistical Bands (Calculated globally)
            eh, el , em_dist  = self.calc.ExpectedHighLow( spot=spot)

            # 3. ZG Logic
            zg_strike   = self.calc.ZG_Strike( spot =spot, df =data , eh=eh, el=el ) 

            # Target Math: VH/VL anchored directly to ZG using 25% of EM Distance
            vh , vl     = self.calc.VolatilityHighLow( zg_strike=zg_strike,spot=spot, em_dist=em_dist) 
            
            
            #Build the Call/Put wall entries
            cw_data , pw_data = self.calc.WallsData( df=data, spot=spot)
            sides    = [("calls",cw_data ),
                          ( "puts" , pw_data)
                        ]
            
            for side in sides :          
                temp, _ = self.Walls( wallData=side[1], side=side[0], is_future=is_future, spot=spot )
                walls += temp 
            
            walls.sort(key=lambda x: float(str(x).split(',')[0].replace("'","").replace('[','')), reverse=True)
            

            payload = self.Payload(data, walls , is_future , eh, el , em_dist, zg_strike , spot, vh , vl )
        except: 
            print("\t\t|EXCEPTION: TradingViewPayload::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
        
        return payload

    

    def Payload( self, data : DataFrame, walls : list ,is_future : bool, eh : float, el:float , em_dist:float, zg_strike : float, spot: float,vh: float , vl:float) -> str :
        """
            Assembling the Payload string
            PARAMETERS  :
            RETURNS     :
                            str - TradingView formatted string 
        """
        payload = [] 
        try:
            payload.append(f"L:{round(zg_strike, 2)},ZG,ZERO GAMMA,Zero Gamma~Dealer gamma flips here~Price magnet")
            payload.append(f"{round(spot, 2)},MP,MAX PAIN,Max Pain~Strike with max OI~Expiry target")
            payload.append(f"{round(eh, 2)},EH,EM HIGH,Expected Move HIGH~1-sigma upper bound")
            payload.append(f"{round(el, 2)},EL,EM LOW,Expected Move LOW~1-sigma lower bound")
            payload.append(f"{round(vh, 2)},VH,VOL HIGH,Vol Band HIGH~ZG + 25% EM")
            payload.append(f"{round(vl, 2)},VL,VOL LOW,Vol Band LOW~ZG - 25% EM")
        except:
            print("\t\t|EXCEPTION: TradingViewPayload::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
        

        return ";".join(  payload + walls)


    def Walls ( self, wallData : DataFrame, side :str , is_future : bool  ,spot : float, outDF : DataFrame = pd.DataFrame({}) ) -> ( DataFrame, DataFrame) :
        """
            Create a list of side walls ( calls /puts )
            PARAMETERS  :
                            wallData   [ Dataframe ] - data for the specific side
                            side       [ str ]       - identify which side working on
                            is_future  [ bool ]      - identifies if symbol is futures or not
                            spot       [ float ]     - spot price of asset
                            outDF      [ DataFrame ] - DataFrame containing updated market data 
            RETURNS     :
                            Dataframe 
        """
        s ,g ,liq   = 0,0,0
        walls       = []
        try:
            for _, row in wallData.iterrows():
                s, g , liq              = row['strikeprice'], row['gex'] , row['liquidity']
                dist_points             = ((s / spot) - 1) * 100 if is_future else  s - spot
                g_mill                  = round(g / 1000000, 1)
                line_val                = g_mill if abs(g_mill) > 0 else round(liq / 100, 1)
                g_sign                  = "+" if g_mill >= 0 else ""
                if not outDF.empty:
                    outDF['dist_points']    = dist_points 
                    outDF['g_sign']         = g_sign
                    outDF['g_mil']          = g_mil
                temp =(f"{round(s, 2)},{'PW' if side == 'puts' else 'CW'},{'Put' if side == 'puts' else 'Call'} Wall, " +
                             f"Strike: {int(s)}~GEX: {g_sign}{g_mill}M~From spot: {dist_points:+.2f}")                
                walls.append( temp )
            
        except: 
            print("\t\t|EXCEPTION: TradingViewPayload::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
        
        return walls, outDF
    
    def TvStringFromDict(self,  data : dict , benchMarks : dict  )-> str:
        """
            Format data from the dictionary into the TradingView string format
            PARAMETERS :
                            data        [ dict ] - levels for the symbol
                            benchMarcks [ dict ] - extraneous level info to be added to tvstring 
            RETURNS    :
                            str
        """
        details     = {'EH' :'EM HIGH','EL' :'EM LOW', 'VH' :'VOL HIGH','VL':'VOL LOW'}
        tvString    = ""
        
        try:
            print("[ * ] Building TradingView String   ")
            
            if not(data is None or data == {} ):            
                for key in data['data'] :
                    tvString    += ';' if len(tvString) > 0 else ''
                    seg         = data['data']
                    if seg[key]['abbrev'] in Extraneous_Levels :                    
                        tvString += (f"{key},{seg[key]['abbrev']},{details[ seg[key]['abbrev'] ]}," +
                                        f"{seg[key].get('comments','')} CW={seg[key].get('cw_size',0):.1f}M | PW={seg[key].get('pw_size',0):.1f}M" )
                        del benchMarks[ seg[key]['abbrev'] ]
                    elif seg[key]['abbrev'] in ['ZG','MP'] :
                        tvString += (f"{key},{seg[key]['abbrev']},{seg[key]['level']}," +
                                     f"{seg[key].get('comments','')} CW={seg[key].get('cw_size',0):.1f}M | PW={seg[key].get('pw_size',0):.1f}M" )
                    else:
                        tvString += (f"{key},{seg[key]['abbrev']},{seg[key]['level']}," +
                                    f"CW={seg[key].get('cw_size',0):.1f}M | PW={seg[key].get('pw_size',0):.1f}M " +
                                     f" Strength:{seg[key]['strength']} Source:{seg[key]['source']}" )
            if benchMarks != {}:
                for key in benchMarks:
                    tvString    += ';' if len(tvString) > 0 else ''
                    tvString    += (f"{benchMarks[key]},{key},{details[key]},{details[key]} ")
        except:
            print("\t\t|EXCEPTION: CorrelatedLevels::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
        finally:
            if False :            
                for lvl in data['data']:
                    print(f"[DEBUG] {data['symbol']} -> {lvl} -> {data['data'][lvl] } " )

        return "L:"+tvString 

if __name__ == "__main__":
    
    spot = 7418.3    
    data = [
                {'strikeprice':7400.0,  'liquidity':3363.0, 'side':'calls', 'gex':2488620.0},
                {'strikeprice':7425.0,  'liquidity':894.0,  'side':'calls', 'gex':663795.0},
                {'strikeprice':7375.0,  'liquidity':529.0,  'side':'calls', 'gex':390137.5},
                {'strikeprice':7450.0,  'liquidity':505.0,  'side':'calls', 'gex':376225.0},
                {'strikeprice':7350.0,  'liquidity':1659.0, 'side':'calls', 'gex':1219365.0},
                {'strikeprice':6480.0,  'liquidity':2.0,    'side':'puts', 'gex':-1296.0},
                {'strikeprice':6475.0,  'liquidity':5.0,    'side':'puts', 'gex':-3237.5},
                {'strikeprice':6470.0,  'liquidity':12.0,   'side':'puts', 'gex':-7764.0},
                {'strikeprice':8350.0,  'liquidity':11.0,   'side':'puts', 'gex':-9185.0},
                {'strikeprice':6465.0,  'liquidity':1.0,    'side':'puts', 'gex':-646.5 }
              ]
    payload = TradingViewPayload()

    print( f"[DEBUG] Payload : { payload.Build( data=pd.DataFrame(data), symbol='ESM26', spot=spot ) } " ) 
