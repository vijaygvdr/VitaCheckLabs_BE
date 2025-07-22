#!/usr/bin/env python3
"""
Optimize DynamoDB costs by reducing capacity to free tier limits
This script reduces RCU/WCU to stay within AWS free tier (25 RCU + 25 WCU)
"""

import boto3
import time

def optimize_table_capacity():
    """Reduce DynamoDB table capacity to free tier limits"""
    
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    
    # Optimized capacity settings for free tier
    optimizations = {
        'vitachecklabs-users': {
            'main': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 2},
            'gsi': {
                'email-index': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 1},
                'username-index': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 1}
            }
        },
        'vitachecklabs-lab-tests': {
            'main': {'ReadCapacityUnits': 3, 'WriteCapacityUnits': 1},
            'gsi': {
                'code-index': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 1},
                'category-price-index': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 1}
            }
        },
        'vitachecklabs-reports': {
            'main': {'ReadCapacityUnits': 3, 'WriteCapacityUnits': 3},
            'gsi': {
                'user-status-index': {'ReadCapacityUnits': 3, 'WriteCapacityUnits': 2},
                'test-status-index': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 1},
                'report-number-index': {'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
            }
        },
        'vitachecklabs-bookings': {
            'main': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 2},
            'gsi': {
                'user-date-index': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 1},
                'test-date-index': {'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1},
                'reference-index': {'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
            }
        }
    }
    
    total_rcu = 0
    total_wcu = 0
    
    for table_name, config in optimizations.items():
        print(f"📉 Optimizing {table_name}...")
        
        try:
            # Update main table
            main_config = config['main']
            total_rcu += main_config['ReadCapacityUnits']
            total_wcu += main_config['WriteCapacityUnits']
            
            dynamodb.update_table(
                TableName=table_name,
                ProvisionedThroughput=main_config
            )
            print(f"  ✓ Main table: {main_config['ReadCapacityUnits']} RCU, {main_config['WriteCapacityUnits']} WCU")
            
            # Update GSIs
            gsi_updates = []
            for gsi_name, gsi_config in config['gsi'].items():
                total_rcu += gsi_config['ReadCapacityUnits']
                total_wcu += gsi_config['WriteCapacityUnits']
                
                gsi_updates.append({
                    'Update': {
                        'IndexName': gsi_name,
                        'ProvisionedThroughput': gsi_config
                    }
                })
                print(f"  ✓ GSI {gsi_name}: {gsi_config['ReadCapacityUnits']} RCU, {gsi_config['WriteCapacityUnits']} WCU")
            
            # Update all GSIs
            if gsi_updates:
                dynamodb.update_table(
                    TableName=table_name,
                    GlobalSecondaryIndexUpdates=gsi_updates
                )
            
            # Wait a bit between table updates
            time.sleep(2)
            
        except Exception as e:
            print(f"  ❌ Error updating {table_name}: {e}")
    
    print(f"\n💰 OPTIMIZED TOTALS:")
    print(f"Total RCU: {total_rcu} units")
    print(f"Total WCU: {total_wcu} units")
    
    if total_rcu <= 25 and total_wcu <= 25:
        print("🎉 NOW WITHIN FREE TIER LIMITS!")
        print("Estimated cost: $0/month")
    else:
        rcu_cost = total_rcu * 0.00013 * 24 * 30
        wcu_cost = total_wcu * 0.00065 * 24 * 30
        total_cost = rcu_cost + wcu_cost
        print(f"Estimated cost: ${total_cost:.2f}/month")
    
    print(f"\n⏰ Note: Changes may take 5-10 minutes to take effect")

if __name__ == "__main__":
    optimize_table_capacity()