## ###################################################################################################################
##  Program :   ConfluenceEngine
##  Author  :   Sean Burner
##  Detail  :   Finds the confluence levels among related assets ( SPY/SPX/ESM26)
##  Install :   
##  Example :
##              python3 
##              python3 
##  Notes   :   https://docs.python.org/3/tutorial/classes.html
## #############################################################################
import re
import sys
import pickle
import getpass
import inspect
import pandas   as pd
import numpy    as np

from pandas                     import DataFrame 
from pathlib                    import Path

from Calculations               import Calculations
from TradingViewPayload         import TradingViewPayload

Extraneous_Levels = ['VH','VL','EH','EL']   # needs to be centralized, also in TradingViewPayload 

class ConfluenceEngine:
    def __init__(self, proximity_threshold_points=15.0):
        # Maximum distance in SPX points to consider multiple lines a "cluster"
        self.threshold = proximity_threshold_points
        self.calc      = Calculations()

    def NormalizeValues( self,data : dict , base : str)->( dict, dict ):
        """
            Normalize the values so they can fit on the same chart . Normalized against first symbol entry in dictionary 
            PARAMETERS  :
                            data [ dict ] - symbol indexed dictionary with market data
                            base [str ]   - symbol to normalize the other symbols to 
            RETURNS     :
                            dict  - processed dictionary of symbols 
        """
        symbols     = list(data.keys())
        bnchKeys    = ['EH','EL','VH','VL']
        benchmarks  = { }
        multiplier  = 1
        newKeyValue = 0
        
        try:
            if data is None  or data == {}:
                print("[ * ] Normalizing values - ERROR - No Data ")
                return data,{}

            print(f"[ * ] Normalizing values on { base } " )
            
            for lvl in list(data[base]['data'].keys()):
                for bKey in bnchKeys:
                    if data[base]['data'][lvl]["abbrev"] == bKey:
                        benchmarks.update( { bKey : lvl } )
                        
            symbols.remove( base)
            for pos, symbol in enumerate( symbols ) :                
                multiplier  = data[base]['spot']/data[symbol]['spot']  #10 if data[base]['spot'] < 1_000  else data[base]['spot']/data[symbol]['spot']     # trying to account for SPY  type assets  symbol =="SPY"                
                temp        = {}
                for key,values in data[symbol]['data'].items() :
                    newKeyValue  =  round(float(key*multiplier) ,2)
                    temp.update( { newKeyValue : data[symbol]['data'][key]})
                    print(f"[DEBUG] {newKeyValue} : { data[symbol]['data'][key]} ")
                    if values['abbrev'] in Extraneous_Levels :
                        if ( values['abbrev'][1].upper() =='H' and newKeyValue > benchmarks.get(values['abbrev'],0) ) :
                             benchmarks.update({values['abbrev']: newKeyValue})
                        elif ( values['abbrev'][1].upper() =='L' and newKeyValue < benchmarks.get(values['abbrev'],1_000_000) ):
                             benchmarks.update({values['abbrev']: newKeyValue })
                   
                data[symbol]['data'] = temp                
        except:
            print("\t\t|EXCEPTION: CorrelatedLevels::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
        finally:
            if False :
                for sym in data :
                    for lvl in data[sym]['data']:
                        print(f"[DEBUG] {sym} -> {lvl} -> {data[sym]['data'][lvl] } " )
                        
        return data ,benchmarks

    def ConsolidateLevels ( self, data : dict , baseSym : str) -> dict:
        """
            Consolidate symbol levels to the base dictionary
            PARAMETERS  :
                            data      [ dict ] - processed symbol and market data
                            baseSym   [str ]   - symbol to normalize the other symbols to 
            RETURNS     :
                            DataFrame
        """
        dKeys   = None
        base    = None
        nKeys   = None
        
        try:
            def UpdateBaseDict( base : dict , bKey : float , rec : dict ) -> dict:
                """
                    Update the base record with the record to be added/updated
                    PARAMETERS  :
                                    base   [ dict ]  - base record
                                    bKey   [ float ] - base record key to update record to 
                                    rec    [ dict ]  - level entry to be added to base record 
                    RETURNS     :
                                    dict
                """
                try:
                    base['data'][bKey].update( { 'cw_size' :  base['data'][bKey].get('cw_size',0)+ rec.get('cw_size', 0.00) })
                    base['data'][bKey].update( { 'pw_size' :  base['data'][bKey].get('pw_size',0)+ rec.get('pw_size', 0.00) })
                    base['data'][bKey]['source']        += f"/{rec.get('source','') }"
                    base['data'][bKey]['strength']      += 1
                except:
                    print("\t\t|EXCEPTION: CorrelatedLevels::UpdateBaseDict::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
                    for entry in sys.exc_info():
                        print("\t\t >>   " + str(entry) ) 
                return base

            
            if data is None or data == {}:
                print("[ * ] Consolidating Levels - ERROR - No Data ")
                return data

            print("[ * ] Consolidating Levels  ")

            dKeys = list( data.keys() )
            #SET UP THE BASE SYMBOL FIRST 
            base = data[baseSym]
            base.update( {'symbol': baseSym })
            nKeys = { int(float(dKey)/10) :dKey for dKey in list(data[baseSym]['data'].keys()) }
            dKeys.remove( baseSym)
            for pos, key in enumerate ( dKeys):            
                lvls = data[key]['data']
                for key,value in lvls.items():
                    if  lvls[key]['abbrev'] in ['CW','PW']:
                        if key in base['data']  or int(key/10) in nKeys:
                            tKey = key if key in base['data'] else nKeys[int(key/10)]
                            base = UpdateBaseDict( base = base , bKey=tKey , rec=lvls[key] )
                            """
                            base['data'][tKey].update( { 'cw_size' :  base['data'][tKey].get('cw_size',0)+ lvls[key].get('cw_size', 0.00) })
                            base['data'][tKey].update( { 'pw_size' :  base['data'][tKey].get('pw_size',0)+ lvls[key].get('pw_size', 0.00) })
                            base['data'][tKey]['source']        += f"/{lvls[key]['source']}"
                            base['data'][tKey]['strength']      += 1
                            """
                        else:
                            found   = False
                            seleLvl = None 
                            for lvl  in list( base['data'].keys()):
                                if self.threshold >= abs(lvl - key)  :
                                    found   = True
                                    seleLvl = lvl
                            if found :
                                base = UpdateBaseDict( base = base , bKey=seleLvl , rec=lvls[key] )
                                """
                                base['data'][seleLvl].update( { 'cw_size' :  base['data'][seleLvl].get('cw_size',0)+ lvls[key].get('cw_size', 0.00) })
                                base['data'][seleLvl].update( { 'pw_size' :  base['data'][seleLvl].get('pw_size',0)+ lvls[key].get('pw_size', 0.00) })
                                base['data'][seleLvl]['source']        += f"/{lvls[key]['source']}"
                                base['data'][seleLvl]['strength']      += 1
                                """
                            else: 
                                base['data'].update( { key : lvls[key] })
                                nKeys.update( { int(key/10) : key })
        except:
            print("\t\t|EXCEPTION: CorrelatedLevels::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) ) 
        finally:
            if False :            
                for lvl in base['data']:
                    print(f"[DEBUG] {base['symbol']} -> {lvl} -> {base['data'][lvl] } " )

                print(f"[DEBUG] Normalized Keys : { nKeys }")
        
        return base 
    
    def BuildDictFromData( self, ticker : list, cw_data:DataFrame, pw_data: DataFrame, zg_strike: float , eh:float,el:float, vh:float, vl:float) -> dict:
        """
            Build the templated dictionary from the market data dataframe
            PARAMETERS :
                            ticker   [ list ]       - symbol ( str)  and spot ( float )
                            cw_data  [ DataFrame ]  - call wall levels data
                            pw_data  [ DataFrame ]  - put wall levels data
                            zg_strike[ float ]      - zero gamma strike price
                            eh       [ float ]      - estimated move high
                            el       [ float ]      - estimated move low
                            vh       [ float ]      - volatility high
                            vl       [ float ]      - volatility low 
            RETURNS    :
                            dictionary
        """
        data    = {'data':{}}
        details = [ ('ZG','ZERO GAMMA'  ,'Zero Gamma~Dealer gamma flips here~Price magnet'),
                    ('EH','EM High'     ,'Expected Move HIGH~1-sigma lower bound'),
                    ('EL','EM Low'      ,'Expected Move LOW~1-sigma lower bound'),
                    ('VH','VOL High'    ,'Vol Band HIGH~ZG + 25% EM'),
                    ('VL','VOL Low'     ,'Vol Band Low~ZG + 25% EM')
                ]
        try:
            print(f"[ * ] Building Dictionary for {ticker[0] }   ")
            for pos, lvl in enumerate( [ zg_strike,eh, el, vh, vl ] ):
                data['data'].update( { round(lvl,2): {   'pw_size' : 0.0,
                                                'cw_size' : 0.0,
                                                'strength': 1,
                                                'source'  : ticker[0],
                                                'abbrev'  : details[pos][0],
                                                'level'   : details[pos][1],
                                                'comments': details[pos][2]
                                                                   } }  )
            for level in [["c", cw_data], ["p",pw_data]  ] :
                for pos, row  in level[1].iterrows(  ) :
                    gex = abs( round(row['gex'] /1_000_000, 2)  )
                    #if row['strikeprice'] in data['data']:
                    if not ( round(row['strikeprice'],0) in data['data']):
                        data['data'].update( { round(row['strikeprice'],0): {'pw_size': ( gex if level[0] =="p" else 0.0),
                                                                    'cw_size' : ( gex if level[0] =="c" else 0.0),
                                                                    'strength': 1,
                                                                    'source'  : ticker[0],
                                                                    'abbrev'  :'CW' if level[0] =='c' else 'PW',
                                                                    'level'   : 'Call Wall' if level[0] =='c' else 'Put Wall',
                                                                    'comments':f'Strike: {row["strikeprice"]} ~GEX: {gex} M~From spot: -{ ticker[1]-row["strikeprice"]}'
                                                                   } }  )
                   

                    
        except:
            print("\t\t|EXCEPTION: CorrelatedLevels::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
        finally:
            if False:
                print (f"[DEBUG] Symbol : {ticker[0] }  Dictionary : {data} ")

        return data 

    def LoadFileData( self,fileName : str)->dict:
        """
            Load process tv strings into a level keyed dictionary
            PARAMETERS  :
                            fileName [str ]  name of 
            RETURNS     :
                            dictionary - multilayered dictionary for each symbol file found indexed by symbol name with spot 
        """
        data        = {}
        symbol      = ""
        fieldNames  = ['','abbrev','level','comments','size']
        
        try:
            print(f"[ * ] LoadFileData - Reading from { fileName}")
                   
            fDict       = {}
            symbol      = fileName.stem      
            with open(fileName, 'r') as file:
                content = file.read()                
                content = content.split("L:")[1]
                if len( content) < 2:
                    print(f"[ * ] ERROR Malformed data in  { fileName}")
                    return data 
                rows    = content.split(";")
                for row in rows:                    
                    fields  = row.split(",")
                    keyLvl  = round(float(fields[0]),2)
                    match   = "".join( re.findall(r"(\d+?.\d+)M",fields[3]) )
                    if ( keyLvl in fDict ) :
                        wType = 'cw_size' if fields[1]=='CW' else 'pw_size'                       
                        fDict[ keyLvl ].update( { wType : fDict[ keyLvl ].get(wType, 0.00) + float(0 if match =='' else match)  ,  'strength' :  fDict[keyLvl]['strength'] +1} ) 
                    else:
                        for pos,field in enumerate( fields):
                            if pos == 0 :                            
                                fDict.update( { keyLvl : { 'cw_size' if fields[1]=='CW' else 'pw_size' : float(match) if match else 0.00 , 'strength' : 1 , 'source':symbol}} ) 
                            else:
                                fDict[ keyLvl ].update( { fieldNames[pos] : field  } ) 
                    
                data.update({  'data':fDict}) #{symbol : {  'data':fDict}})
        except:
            print("\t\t|EXCEPTION: ConfluenceEngine::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
        finally:
            if False :
                for sym in data :
                    for lvl in data[sym]['data']:
                        print(f"[DEBUG] {sym} -> {lvl} -> {data[sym]['data'][lvl] } " )
        
        return  data
def UseDataFiles()->str:
    """
        Use data  files (.rtf ) that already contain the GEX strings
        PARAMETERS  :
        RETURNS     :
                        str - consolidated TradingView String
    """       
    files       = None 
    data        = {}
    base        = ""
    spots       = {'ESM26': 7494.75,   'SPY': 746.48, 'SPX':7481.0} # testing 
    confl       = ConfluenceEngine(proximity_threshold_points=12.0)
    tvString    = ""
    tvPayload   = TradingViewPayload()
    benchmarks  = None 
    
    try:
        print("\t\t Using Data Files as input   ")
        dirPath             = "data/" #input("Where are the data files located: " )
        fileExt             = "rtf"  #input("What is the file extension for the data file(s) [csv, dat,rtf ] : ")
        files               =  {f.stem:f  for f in Path(dirPath).iterdir()  if f.suffix =="."+fileExt }
        
        data.update( { key: confl.LoadFileData( fileName=value) for key,value in files.items() }  )

        base = "ESM26"        
              
        for sym in data:            
            data[sym].update( { 'spot' : spots[sym] }) #  TEST MODE barChart.SpotPrice()
            
        
        data, benchMarks    = confl.NormalizeValues( data ,base )       
        data                = confl.ConsolidateLevels( data, base )
        tvString            = tvPayload.TvStringFromDict( data, benchMarks )

        
    except:
        print("\t\t|EXCEPTION: CorrelatedLevels::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
        for entry in sys.exc_info():
            print("\t\t >>   " + str(entry) )

    return tvString



def UserProvidedSymbols()-> str :
    """
        Orchestrator for getting list of symbols from user to correlate
        PARAMETERS  :
                        None
        RETURNS     :
                        str - TradingView GEX Indicator formatted string
    """
    base            = ''
    data            = {}
    calc            = Calculations()
    confl           = ConfluenceEngine(proximity_threshold_points=12.0)
    tickers         = []
    tvString        = ""
    is_future       = False 
    defaultDF       = { 'strikeprice':0, 'liquidity':0 }
    tvPayload       = TradingViewPayload()
    test_ticker     = [ ['ESM26', 7590.25], ['SPY', 755.78], ['SPX', 7582.36] ]  # test 
    master_levels   = []
    try:
        print("\t\t Getting input from User  ")
        
        tickerFromUser  = 'ESM26,SPY,SPX' #input ("Provide assets to be correlated separated by commmas: " )
        symbols         = tickerFromUser.split(",")
        base            = symbols[0]
        
        # Get SPOT , for better multiplier calc do it as quickly as possible 
        for pos, ticker in enumerate(symbols):
            print(f"[ * ] Getting Spot for : {ticker}")            
            temp         = test_ticker[pos]
            spot         = test_ticker[pos][1]
            tickers.append( temp )
         
        #print(f"[DEBUG] Symbols and Spots : { tickers} ")

        #Get Market Data
        cw_data = pd.DataFrame( )       
        pw_data = pd.DataFrame( ) 
        for pos, ticker in enumerate(tickers):            
            #barChart    = BarChartAPI( symbol = tickers[pos][0] )
            #df          = barChart.MarketData()
                    
            #with open(f"data/{ticker[0]}.pkl", "wb") as file :
            #    pickle.dump( df, file )
                
            with open(f"data/{ticker[0]}.pkl", "rb") as file :
                df = pickle.load(  file )           

                
            
            df['source']    = ticker[0]
            df              = calc.Greeks_And_Gex( df=df , spot=tickers[pos][1])
            # 1. Clean and Numeric
            df              = calc.DataCleaning( df=df)
            df, is_future   = calc.FuturesStrikePrice(symbol=ticker[0], data=df, spot=ticker[1])
            if pos == 0: # ONLY CALCULATE FOR BASE ASSET
                eh, el , em_dist   = calc.ExpectedHighLow( spot=spot)
                zg_strike          = calc.ZG_Strike( spot =spot, df =df , eh=eh, el=el )                
                vh , vl            = calc.VolatilityHighLow( zg_strike=zg_strike,spot=spot, em_dist=em_dist) 

                                   
            cw_data, pw_data    = calc.WallsData(df =df, spot=spot)
            
            #with open(f"data/{ticker[0]}_cw.pkl", "rb") as file :
            #    cw_data = pickle.load(  file )
            #with open(f"data/{ticker[0]}_pw.pkl", "rb") as file :
            #    pw_data = pickle.load(  file )
            
            #with open(f"data/{ticker[0]}_cw.pkl", "wb") as file :
            #    pickle.dump( cw_data, file )
            #with open(f"data/{ticker[0]}_pw.pkl", "wb") as file :
            #    pickle.dump( pw_data, file )
            
            temp    = confl.BuildDictFromData( ticker = ticker, cw_data=cw_data, pw_data=pw_data, zg_strike=zg_strike, eh=eh,el=el, vh=vh, vl=vl)
            
            #df.to_csv( f"data/{ticker[0]}.csv")

            data.update( {ticker[0] : temp } )
            data[ticker[0]].update( { 'source': ticker[0], 'spot' :  ticker[1] })
        
        data, benchMarks    = confl.NormalizeValues( data ,base )       
        data                = confl.ConsolidateLevels( data, base )
        tvString            = tvPayload.TvStringFromDict( data, benchMarks )

  
    except:
        print("\t\t|EXCEPTION: CorrelatedLevels::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
        for entry in sys.exc_info():
            print("\t\t >>   " + str(entry) )

    return tvString 

def main():
    """
        Main logic to run ConfluenceEngine in test mode 
    """
    # Run using data files 
    tvString = UseDataFiles()
    print(f"\n\t********************* TRADING VIEW *************************\n{tvString}")

    # Run with symbols from user
    tvString = UserProvidedSymbols()
    print(f"\n\t********************* TRADING VIEW *************************\n{tvString}")

if __name__ == "__main__":
    main()
