import re

class ConfluenceEngine:
    def __init__(self, proximity_threshold_points=15.0):
        # How close levels must be on the SPX scale to count as a confluence
        self.threshold = proximity_threshold_points

    def parse_payload_string(self, payload_str, asset_type):
        """
        Parses a standard TradingView payload string back into a list of dictionaries.
        Normalizes SPY prices to SPX scale.
        """
        levels = []
        # Split by coordinate separator
        segments = payload_str.replace("L:", "").split(";")
        
        for segment in segments:
            if not segment:
                continue
            parts = segment.split(",")
            try:
                raw_price = float(parts[0])
                label = parts[1]
                full_label = parts[2]
                desc = parts[3]
                
                # Extract weight/GEX numeric value if present
                weight = float(parts[4]) if len(parts) > 4 else 0.0
                
                # Normalize SPY to SPX scale
                normalized_price = raw_price * 10.0 if asset_type.upper() == "SPY" else raw_price
                
                levels.append({
                    "raw_price": raw_price,
                    "normalized_price": normalized_price,
                    "label": label,
                    "full_label": full_label,
                    "desc": desc,
                    "weight": weight,
                    "origin_asset": asset_type.upper()
                })
            except Exception:
                continue # Skip errors or malformed lines safely
        return levels

    def find_confluences(self, spy_payload, spx_payload, esm_payload):
        """
        Combines all assets, groups levels that are close to each other,
        and identifies high-probability confluence zones.
        """
        # 1. Parse and normalize all payloads
        all_levels = []
        all_levels.extend(self.parse_payload_string(spy_payload, "SPY"))
        all_levels.extend(self.parse_payload_string(spx_payload, "SPX"))
        all_levels.extend(self.parse_payload_string(esm_payload, "ESM26"))
        
        # Sort all levels globally by their normalized SPX price
        all_levels.sort(key=lambda x: x["normalized_price"])
        
        confluence_zones = []
        used_indices = set()
        
        # 2. Greedy clustering algorithm to find overlaps
        for i in range(len(all_levels)):
            if i in used_indices:
                continue
                
            cluster = [all_levels[i]]
            used_indices.add(i)
            
            # Look forward to find any other levels within our point threshold
            for j in range(i + 1, len(all_levels)):
                if j in used_indices:
                    continue
                if abs(all_levels[j]["normalized_price"] - all_levels[i]["normalized_price"]) <= self.threshold:
                    cluster.append(all_levels[j])
                    used_indices.add(j)
            
            # 3. If multiple assets show a level here, it's a confluence zone
            if len(cluster) >= 2:
                # Calculate the average price of the cluster on the SPX scale
                avg_spx_price = sum(item["normalized_price"] for item in cluster) / len(cluster)
                assets_involved = list(set(item["origin_asset"] for item in cluster))
                labels_involved = [f"{item['origin_asset']}-{item['label']}" for item in cluster]
                
                confluence_zones.append({
                    "spx_scale_price": avg_spx_price,
                    "assets_count": len(assets_involved),
                    "labels": ", ".join(labels_involved),
                    "items": cluster
                })
                
        # Sort zones by importance (how many levels clustered there), then by price descending
        confluence_zones.sort(key=lambda x: (x["assets_count"], x["spx_scale_price"]), reverse=True)
        return confluence_zones

    def generate_tv_output(self, zones, target_asset, current_spot):
        """
        Maps the discovered confluences back into the scale of your target asset 
        and formats it cleanly for your TradingView parser.
        """
        output_segments = []
        
        for idx, zone in enumerate(zones):
            spx_price = zone["spx_scale_price"]
            
            # Map back to target asset's native scale
            if target_asset.upper() == "SPY":
                target_price = spx_price / 10.0
            else:
                target_price = spx_price # SPX and ESM26 are on the same 1:1 scale
                
            dist_pct = ((target_price / current_spot) - 1) * 100
            
            # Format according to your institutional target string spec
            prefix = "L:" if idx == 0 else ""
            segment = (
                f"{prefix}{round(target_price, 2)},CF,CONFLUENCE,"
                f"Strength: {zone['assets_count']} Assets~"
                f"Clusters: {zone['labels']}~"
                f"Dist: {dist_pct:+.2f}%,0"
            )
            output_segments.append(segment)
            
        return ";".join(output_segments)

    
if __name__ == "__main__":
    # Target Strings from your previous runs
    spy_data = "L:735.0,ZG,ZERO GAMMA...[your full SPY payload string here]"
    spx_data = "L:7345.0,ZG,ZERO GAMMA...[your full SPX payload string here]"
    esm_data = "L:7500.0,ZG,ZERO GAMMA...[your full ESM26 payload string here]"
    
    engine = ConfluenceEngine(proximity_threshold_points=15.0)
    
    # 1. Find the overlaps
    zones = engine.find_confluences(spy_data, spx_data, esm_data)
    
    # 2. Map them onto your target chart (e.g., mapping onto ESM26 at 7445.75 spot)
    target_chart = "ESM26"
    current_spot = 7445.75
    
    tv_payload = engine.generate_tv_output(zones, target_chart, current_spot)
    print("\n--- CONFLUENCE PAYLOAD FOR TRADINGVIEW ---")
    print(tv_payload)
