# training/train_rewriter_model.py
import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForSeq2SeqLM, 
    Seq2SeqTrainingArguments, 
    Seq2SeqTrainer,
    DataCollatorForSeq2Seq
)
from datasets import Dataset
import json
import os
import logging
import gc

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RumorRewriterTrainer:
    def __init__(self, model_name="VietAI/vit5-base"):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        
    def load_data(self, data_path, max_samples=11000):
        """Load dữ liệu với tối ưu hóa bộ nhớ"""
        logger.info(f"Loading data from {data_path} (max: {max_samples} samples)")
        
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Data file {data_path} not found")
        
        data = []
        with open(data_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= max_samples:
                    break
                if line.strip():
                    try:
                        item = json.loads(line)
                        if 'original' in item and 'rewriter' in item:
                            data.append({
                                'original': item['original'],
                                'rewriter': item['rewriter']
                            })
                    except Exception as e:
                        logger.debug(f"Skipping invalid line: {e}")
                        continue
        
        logger.info(f"Loaded {len(data)} training examples")
        
        if len(data) < 100:
            raise ValueError(f"Not enough data: {len(data)} samples (need at least 100)")
        
        # Chia tập train/validation
        split_idx = int(0.9 * len(data))
        train_data = data[:split_idx]
        val_data = data[split_idx:]
        
        # Giải phóng bộ nhớ
        del data
        gc.collect()
        
        train_dataset = Dataset.from_list(train_data)
        val_dataset = Dataset.from_list(val_data)
        
        logger.info(f"Train: {len(train_data)}, Val: {len(val_data)} samples")
        return train_dataset, val_dataset
    
    def setup_model(self):
        """Khởi tạo model với cài đặt tối ưu tốc độ"""
        logger.info(f"Loading model: {self.model_name}")
        
        try:
            # Tải tokenizer nhanh
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name, 
                use_fast=True,
                clean_up_tokenization_spaces=False  # Tăng tốc tokenization
            )
            
            # Tải model KHÔNG sử dụng safetensors - SỬA LỖI Ở ĐÂY
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
                use_safetensors=False  # QUAN TRỌNG: Tắt safetensors
            )
            
            logger.info("Model loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            # Thử phương pháp dự phòng
            try:
                logger.info("Trying alternative loading method...")
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
                logger.info("Model loaded with alternative method")
            except Exception as e2:
                logger.error(f"Alternative loading also failed: {e2}")
                raise
    
    def preprocess_function(self, examples):
        """Tiền xử lý dữ liệu tối ưu"""
        inputs = [str(x) for x in examples['original']]
        targets = [str(x) for x in examples['rewriter']]
        
        # Tokenize inputs
        model_inputs = self.tokenizer(
            inputs, 
            max_length=128,
            truncation=True, 
            padding=False,
            add_special_tokens=True,
            return_tensors=None
        )
        
        # Tokenize targets với text_target
        labels = self.tokenizer(
            text_target=targets,
            max_length=128,
            truncation=True, 
            padding=False,
            add_special_tokens=True
        )
        
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    def train(self, data_path, output_dir="./trained_rewriter_model"):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        
        try:
            # Load dữ liệu - GIỮ NGUYÊN số lượng mẫu
            train_dataset, val_dataset = self.load_data(data_path, max_samples=11000)
            
            # Setup model
            self.setup_model()
            
            # TỐI ƯU HÓA TOKENIZATION
            logger.info("Tokenizing training data...")
            tokenized_train = train_dataset.map(
                self.preprocess_function,
                batched=True,
                batch_size=256,  # Giảm xuống để ổn định
                remove_columns=train_dataset.column_names,
                desc="Tokenizing training data",
                load_from_cache_file=False
            )
            
            logger.info("Tokenizing validation data...")
            tokenized_val = val_dataset.map(
                self.preprocess_function,
                batched=True,
                batch_size=256,
                remove_columns=val_dataset.column_names,
                desc="Tokenizing validation data",
                load_from_cache_file=False
            )
            
            # Giải phóng bộ nhớ datasets gốc
            del train_dataset, val_dataset
            gc.collect()
            
            # Data collator với padding tối ưu
            data_collator = DataCollatorForSeq2Seq(
                self.tokenizer,
                model=self.model,
                padding='longest',
                max_length=128,
                return_tensors="pt"
            )
            
            # TRAINING ARGUMENTS TỐI ƯU CHO CPU
            training_args = Seq2SeqTrainingArguments(
                output_dir=output_dir,
                overwrite_output_dir=True,
                
                # CÀI ĐẶT HUẤN LUYỆN TỐI ƯU CHO CPU
                num_train_epochs=1,  # GIẢM xuống 1 epoch để train nhanh
                per_device_train_batch_size=2,  # GIẢM cho CPU
                per_device_eval_batch_size=4,
                gradient_accumulation_steps=16,  # TĂNG để mô phỏng batch lớn
                
                # TỐI ƯU HÓA LEARNING
                learning_rate=2e-5,  # Learning rate nhỏ hơn cho ổn định
                warmup_steps=50,
                weight_decay=0.01,
                max_grad_norm=1.0,
                optim="adamw_torch",
                
                # CÀI ĐẶT ĐÁNH GIÁ & LƯU
                evaluation_strategy="no",  # TẮT eval để tăng tốc
                save_strategy="epoch",
                logging_steps=25,
                report_to=None,
                
                # TỐI ƯU HIỆU NĂNG CPU
                dataloader_num_workers=0,
                dataloader_pin_memory=False,
                remove_unused_columns=True,
                predict_with_generate=False,
                
                # TỐI ƯU TỐC ĐỘ
                dataloader_drop_last=True,
                group_by_length=False,
                
                # TIẾT KIỆM BỘ NHỚ
                fp16=False,
            )
            
            # Trainer với cài đặt tối ưu
            trainer = Seq2SeqTrainer(
                model=self.model,
                args=training_args,
                train_dataset=tokenized_train,
                eval_dataset=tokenized_val,
                data_collator=data_collator,
                tokenizer=self.tokenizer,
            )
            
            # Huấn luyện với xử lý lỗi
            logger.info("Starting training...")
            total_steps = len(tokenized_train) // (training_args.per_device_train_batch_size * training_args.gradient_accumulation_steps) * training_args.num_train_epochs
            logger.info(f"Estimated total steps: {total_steps}")
            logger.info(f"Estimated time: ~{total_steps * 3 / 60:.1f} minutes")
            
            # Huấn luyện
            train_result = trainer.train()
            
            # Lưu model
            trainer.save_model(output_dir)
            self.tokenizer.save_pretrained(output_dir)
            
            logger.info(f"✅ Training completed! Model saved to {output_dir}")
            
            return train_result
            
        except KeyboardInterrupt:
            logger.info("Training interrupted by user")
            try:
                trainer.save_model(output_dir + "_interrupted")
                logger.info("Model saved as interrupted backup")
            except Exception as e:
                logger.error(f"Failed to save interrupted model: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Training error: {e}")
            try:
                trainer.save_model(output_dir + "_backup")
                logger.info("Model saved as backup")
            except:
                pass
            return None
        finally:
            # Giải phóng bộ nhớ
            try:
                del trainer
                gc.collect()
            except:
                pass

def train_rumor_rewriter_model(data_path=None, output_dir="./trained_rewriter_model"):
    """Huấn luyện mô hình viết lại rumor với tối ưu tốc độ"""
    try:
        if data_path is None:
            data_path = "training_data/rumor_rewrite_10000.jsonl"
        
        if not os.path.exists(data_path):
            logger.error(f"Data file not found: {data_path}")
            return False
        
        logger.info("🚀 Starting optimized rumor rewriter training...")
        
        # Sử dụng ViT5-base
        trainer = RumorRewriterTrainer("VietAI/vit5-base")
        result = trainer.train(data_path, output_dir)
        
        if result is not None:
            logger.info("✅ Training completed successfully!")
            return True
        else:
            logger.warning("⚠️ Training completed with warnings or was interrupted")
            return True
        
    except Exception as e:
        logger.error(f"❌ Training failed: {e}")
        return False

if __name__ == "__main__":
    train_rumor_rewriter_model()