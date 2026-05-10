import json
import pandas as pd
from typing import List, Dict
import os
class TrainingDataPreparer:
    def __init__(self, input_file: str = "training_data/stock_sentiment_25000.jsonl"):
        self.input_file = input_file
    
    def load_synthetic_data(self) -> List[Dict]:
        """Đọc dữ liệu synthetic từ file JSONL"""
        data = []
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
            print(f"Loaded {len(data)} samples from {self.input_file}")
        except Exception as e:
            print(f"Error loading synthetic data: {e}")
        return data
    
    def create_training_dataset(self, output_path: str):
        """Copy dữ liệu synthetic sang file output (nếu cần chuẩn hóa thêm thì xử lý tại đây)"""
        data = self.load_synthetic_data()
        
        # Chuẩn hóa format (đảm bảo 4 field: text, label, stock_code, has_stock)
        training_data = []
        for item in data:
            training_data.append({
                "text": item.get("text", ""),
                "label": item.get("label", "neutral"),
                "stock_code": item.get("stock_code", ""),
                "has_stock": bool(item.get("has_stock", False))
            })
        
        with open(output_path, "w", encoding="utf-8") as f:
            for item in training_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        
        print(f"Training dataset saved to {output_path} with {len(training_data)} samples")
        return training_data
    
    def analyze_data_distribution(self):
        """Phân tích phân phối nhãn"""
        data = self.load_synthetic_data()
        label_counts = {}
        with_stock, without_stock = 0, 0
        for item in data:
            label = item.get("label", "neutral")
            label_counts[label] = label_counts.get(label, 0) + 1
            if item.get("has_stock"):
                with_stock += 1
            else:
                without_stock += 1
        
        print("Data distribution:")
        for label, count in label_counts.items():
            print(f"  {label}: {count}")
        print(f"  With stock codes: {with_stock}")
        print(f"  Without stock codes: {without_stock}")
        return label_counts
    
    def export_to_excel(self, jsonl_file_path: str, excel_file_path: str):
        """Xuất JSONL sang Excel"""
        try:
            data = []
            with open(jsonl_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line.strip()))
            df = pd.DataFrame(data)
            expected_columns = ['text', 'label', 'stock_code', 'has_stock']
            for col in expected_columns:
                if col not in df.columns:
                    df[col] = None
            df = df[expected_columns]
            df.to_excel(excel_file_path, index=False, engine='openpyxl')
            print(f"Exported to Excel: {excel_file_path} ({len(df)} rows)")
            return True
        except Exception as e:
            print(f"Error exporting to Excel: {e}")
            return False




# import pandas as pd
# import json
# from typing import List, Dict
# import psycopg2
# from config.database import get_db_connection

# class TrainingDataPreparer:
#     def __init__(self):
#         self.conn = get_db_connection()
    
#     def extract_labeled_data(self) -> List[Dict]:
#         """Trích xuất dữ liệu đã được gán nhãn từ database, chỉ từ post_summary"""
#         cur = self.conn.cursor()
        
#         try:
#             # Thống kê số lượng trước
#             cur.execute("""
#                 SELECT COUNT(*) 
#                 FROM post_summary ps
#                 WHERE ps.cau_quan_trong IS NOT NULL 
#                 AND ps.cam_xuc IN ('TÍCH_CỰC', 'TIÊU_CỰC', 'TRUNG_TÍNH')
#             """)
#             post_count = cur.fetchone()[0]
#             print(f"Post summary count in DB: {post_count}")
            
#             # Lấy dữ liệu
#             cur.execute("""
#                 SELECT 
#                     ps.cau_quan_trong as text,
#                     ps.cam_xuc as sentiment,
#                     ps.confidence_score,
#                     ps.ma_chung_khoan as stock_code,
#                     'post' as source
#                 FROM post_summary ps
#                 WHERE ps.cau_quan_trong IS NOT NULL 
#                 AND ps.cam_xuc IN ('TÍCH_CỰC', 'TIÊU_CỰC', 'TRUNG_TÍNH')
#             """)
            
#             raw_rows = cur.fetchall()
#             print(f"Raw rows from database: {len(raw_rows)}")
            
#             data = []
#             skipped_count = 0
#             for row in raw_rows:
#                 text, sentiment, confidence, stock_code, source = row
                
#                 # Debug từng row nếu cần
#                 if len(data) < 5:  # In 5 row đầu để debug
#                     print(f"Sample row {len(data)+1}: text_len={len(text) if text else 0}, sentiment={sentiment}, confidence={confidence}, stock={stock_code}")
                
#                 if text and sentiment:
#                     data.append({
#                         'text': text,
#                         'sentiment': sentiment,
#                         'confidence': confidence,
#                         'stock_code': stock_code,
#                         'source': source,
#                         'has_stock': stock_code is not None
#                     })
#                 else:
#                     skipped_count += 1
            
#             print(f"Actual data extracted after filtering empty values: {len(data)} rows")
#             print(f"Skipped rows due to empty text/sentiment: {skipped_count}")
            
#             return data
            
#         except Exception as e:
#             print(f"Error extracting labeled data: {e}")
#             return []
#         finally:
#             cur.close()
    
#     def create_training_dataset(self, output_path: str, min_confidence: float = 0.0, include_no_stock: bool = True):
#         """Tạo dataset cho huấn luyện với debug chi tiết"""
#         data = self.extract_labeled_data()
        
#         print(f"=== DEBUG: Starting create_training_dataset ===")
#         print(f"Total data extracted: {len(data)} rows")
        
#         # Debug confidence scores
#         confidences = [item['confidence'] for item in data]
#         print(f"Confidence score range: min={min(confidences):.3f}, max={max(confidences):.3f}")
#         print(f"Average confidence: {sum(confidences)/len(confidences):.3f}")
        
#         # Phân tích phân phối confidence
#         confidence_ranges = {
#             '1.0': 0, '0.9-1.0': 0, '0.8-0.9': 0, '0.7-0.8': 0, 
#             '0.6-0.7': 0, '0.5-0.6': 0, '0.0-0.5': 0
#         }
        
#         for conf in confidences:
#             if conf == 1.0: confidence_ranges['1.0'] += 1
#             elif conf >= 0.9: confidence_ranges['0.9-1.0'] += 1
#             elif conf >= 0.8: confidence_ranges['0.8-0.9'] += 1
#             elif conf >= 0.7: confidence_ranges['0.7-0.8'] += 1
#             elif conf >= 0.6: confidence_ranges['0.6-0.7'] += 1
#             elif conf >= 0.5: confidence_ranges['0.5-0.6'] += 1
#             else: confidence_ranges['0.0-0.5'] += 1
        
#         print("Confidence distribution:")
#         for range_name, count in confidence_ranges.items():
#             percentage = (count / len(data)) * 100
#             print(f"  {range_name}: {count} samples ({percentage:.1f}%)")
        
#         # Lọc theo độ tin cậy
#         filtered_data = [item for item in data if item['confidence'] >= min_confidence]
#         print(f"After confidence filtering (min_confidence={min_confidence}): {len(filtered_data)} samples")
        
#         # Debug: Kiểm tra xem có item nào bị loại không
#         removed_by_confidence = len(data) - len(filtered_data)
#         print(f"Removed by confidence filter: {removed_by_confidence} samples")
        
#         # Lọc dữ liệu không có mã chứng khoán nếu cần
#         if not include_no_stock:
#             before_stock_filter = len(filtered_data)
#             filtered_data = [item for item in filtered_data if item['stock_code'] is not None]
#             removed_by_stock = before_stock_filter - len(filtered_data)
#             print(f"Removed by stock filter: {removed_by_stock} samples")
        
#         print(f"Final dataset size: {len(filtered_data)} samples")
#         print("=== DEBUG: End ===")
        
#         # Chuyển đổi sang format phù hợp
#         training_data = []
#         for item in filtered_data:
#             training_data.append({
#                 'text': item['text'],
#                 'label': self._map_sentiment_label(item['sentiment']),
#                 'stock_code': item['stock_code'],
#                 'has_stock': item['stock_code'] is not None
#             })
        
#         # Lưu thành file
#         with open(output_path, 'w', encoding='utf-8') as f:
#             for item in training_data:
#                 f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
#         # Thống kê
#         with_stock = sum(1 for item in training_data if item['stock_code'] is not None)
#         without_stock = sum(1 for item in training_data if item['stock_code'] is None)
        
#         print(f"Created training dataset with {len(training_data)} samples at {output_path}")
#         print(f"With stock codes: {with_stock}, Without stock codes: {without_stock}")
        
#         return training_data
    
#     def create_separate_datasets(self, output_dir: str, min_confidence: float = 0.5):
#         """Tạo dataset riêng cho dữ liệu có mã chứng khoán và không có mã chứng khoán"""
#         data = self.extract_labeled_data()
        
#         # Lọc theo độ tin cậy
#         filtered_data = [item for item in data if item['confidence'] >= min_confidence]
        
#         # Tách dữ liệu
#         data_with_stock = [item for item in filtered_data if item['stock_code'] is not None]
#         data_without_stock = [item for item in filtered_data if item['stock_code'] is None]
        
#         # Lưu dataset có mã chứng khoán
#         if data_with_stock:
#             stock_output_path = f"{output_dir}/training_data_with_stock.jsonl"
#             with open(stock_output_path, 'w', encoding='utf-8') as f:
#                 for item in data_with_stock:
#                     f.write(json.dumps({
#                         'text': item['text'],
#                         'label': self._map_sentiment_label(item['sentiment']),
#                         'stock_code': item['stock_code']
#                     }, ensure_ascii=False) + '\n')
#             print(f"Created stock dataset with {len(data_with_stock)} samples")
        
#         # Lưu dataset không có mã chứng khoán
#         if data_without_stock:
#             no_stock_output_path = f"{output_dir}/training_data_no_stock.jsonl"
#             with open(no_stock_output_path, 'w', encoding='utf-8') as f:
#                 for item in data_without_stock:
#                     f.write(json.dumps({
#                         'text': item['text'],
#                         'label': self._map_sentiment_label(item['sentiment'])
#                     }, ensure_ascii=False) + '\n')
#             print(f"Created no-stock dataset with {len(data_without_stock)} samples")
        
#         return {
#             'with_stock': data_with_stock,
#             'without_stock': data_without_stock
#         }
    
#     def _map_sentiment_label(self, sentiment: str) -> str:
#         """Ánh xạ nhãn cảm xúc sang format chuẩn"""
#         mapping = {
#             'TÍCH_CỰC': 'positive',
#             'TIÊU_CỰC': 'negative',
#             'TRUNG_TÍNH': 'neutral'
#         }
#         return mapping.get(sentiment, 'neutral')
    
#     def analyze_data_distribution(self):
#         """Phân tích phân phối dữ liệu"""
#         data = self.extract_labeled_data()
        
#         sentiment_counts = {'TÍCH_CỰC': 0, 'TIÊU_CỰC': 0, 'TRUNG_TÍNH': 0}
#         stock_sentiment_counts = {}
#         no_stock_counts = {'TÍCH_CỰC': 0, 'TIÊU_CỰC': 0, 'TRUNG_TÍNH': 0}
        
#         for item in data:
#             sentiment = item['sentiment']
#             stock_code = item['stock_code']
            
#             # Tổng số lượng theo sentiment
#             sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
            
#             # Phân loại theo có mã chứng khoán hay không
#             if stock_code is not None:
#                 if stock_code not in stock_sentiment_counts:
#                     stock_sentiment_counts[stock_code] = {'TÍCH_CỰC': 0, 'TIÊU_CỰC': 0, 'TRUNG_TÍNH': 0}
#                 stock_sentiment_counts[stock_code][sentiment] = stock_sentiment_counts[stock_code].get(sentiment, 0) + 1
#             else:
#                 no_stock_counts[sentiment] = no_stock_counts.get(sentiment, 0) + 1
        
#         print("Overall data distribution:")
#         for sentiment, count in sentiment_counts.items():
#             print(f"{sentiment}: {count} samples")
        
#         print(f"\nWithout stock codes: {sum(no_stock_counts.values())} samples")
#         for sentiment, count in no_stock_counts.items():
#             print(f"  {sentiment}: {count}")
        
#         print(f"\nWith stock codes: {sum(sum(v.values()) for v in stock_sentiment_counts.values())} samples")
#         for stock_code, counts in stock_sentiment_counts.items():
#             total = sum(counts.values())
#             print(f"{stock_code}: Total={total}, Positive={counts.get('TÍCH_CỰC', 0)}, "
#                   f"Negative={counts.get('TIÊU_CỰC', 0)}, Neutral={counts.get('TRUNG_TÍNH', 0)}")
        
#         return sentiment_counts, stock_sentiment_counts, no_stock_counts
    
#     def export_to_excel(self, jsonl_file_path: str, excel_file_path: str):
#         """Xuất file JSONL sang Excel với 4 cột: text, label, stock_code, has_stock"""
#         try:
#             # Đọc dữ liệu từ file JSONL
#             data = []
#             with open(jsonl_file_path, 'r', encoding='utf-8') as f:
#                 for line in f:
#                     if line.strip():
#                         data.append(json.loads(line.strip()))
            
#             # Tạo DataFrame
#             df = pd.DataFrame(data)
            
#             # Đảm bảo có đủ 4 cột cần thiết
#             expected_columns = ['text', 'label', 'stock_code', 'has_stock']
#             for col in expected_columns:
#                 if col not in df.columns:
#                     df[col] = None
            
#             # Chọn chỉ 4 cột cần thiết
#             df = df[expected_columns]
            
#             # Xuất ra Excel
#             df.to_excel(excel_file_path, index=False, engine='openpyxl')
            
#             print(f"Đã xuất file Excel thành công: {excel_file_path}")
#             print(f"Số lượng dòng: {len(df)}")
#             print(f"Các cột: {', '.join(df.columns)}")
            
#             # Thống kê thêm
#             print(f"🏷️ Phân phối nhãn:")
#             label_counts = df['label'].value_counts()
#             for label, count in label_counts.items():
#                 print(f"   {label}: {count} samples ({count/len(df)*100:.1f}%)")
            
#             print(f"📈 Có mã chứng khoán: {df['has_stock'].sum()} samples")
            
#             return True
            
#         except Exception as e:
#             print(f"❌ Lỗi khi xuất file Excel: {e}")
#             return False

# # Sử dụng
# if __name__ == "__main__":
#     preparer = TrainingDataPreparer()
    
#     # Tạo dataset tổng hợp bao gồm cả không có mã chứng khoán
#     preparer.create_training_dataset('training_data_complete.jsonl')
    
#     # Tạo dataset riêng biệt
#     preparer.create_separate_datasets('./datasets')
    
#     # Phân tích phân phối
#     preparer.analyze_data_distribution()