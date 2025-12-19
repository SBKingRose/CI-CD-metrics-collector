"""
AI-powered suggestion generator for diagnostics
Uses free AI APIs (Hugging Face Inference API or OpenAI free tier)
"""
from typing import Dict, Optional
import requests
from app.config import settings


class AISuggestionGenerator:
    def __init__(self):
        self.provider = settings.ai_provider
        self.use_ai = settings.use_ai_suggestions and settings.ai_provider != "none"
        
        if self.provider == "openai" and settings.openai_api_key:
            self.openai_key = settings.openai_api_key
        elif self.provider == "huggingface":
            self.hf_key = settings.huggingface_api_key
        else:
            self.use_ai = False
    
    def enhance_diagnostic(self, diagnostic: Dict) -> str:
        """
        Enhance diagnostic message with AI-generated actionable suggestions
        """
        if not self.use_ai:
            return diagnostic.get("message", "")
        
        base_message = diagnostic.get("message", "")
        diagnostic_type = diagnostic.get("type", "")
        metadata = diagnostic.get("metadata", {})
        
        # Generate AI suggestion
        suggestion = self._generate_suggestion(diagnostic_type, metadata, base_message)
        
        if suggestion:
            return f"{base_message}\n\n💡 Suggestion: {suggestion}"
        
        return base_message
    
    def _generate_suggestion(self, diagnostic_type: str, metadata: Dict, context: str) -> Optional[str]:
        """Generate AI suggestion based on diagnostic type"""
        
        prompt = self._build_prompt(diagnostic_type, metadata, context)
        
        if self.provider == "huggingface":
            return self._query_huggingface(prompt)
        elif self.provider == "openai":
            return self._query_openai(prompt)
        
        return None
    
    def _build_prompt(self, diagnostic_type: str, metadata: Dict, context: str) -> str:
        """Build prompt for AI"""
        
        base_prompt = f"""You are a DevOps expert analyzing CI/CD pipeline issues. 
Given this diagnostic: {context}

Provide a brief, actionable suggestion (1-2 sentences) on how to fix or investigate this issue.
Focus on practical steps an engineer can take immediately.
"""
        
        if diagnostic_type == "regression":
            base_prompt += f"""
The build regressed {metadata.get('regression_percent', 0):.1f}% after commit {metadata.get('commit_hash', '')[:8]}.
What should the engineer check first?
"""
        elif diagnostic_type == "step_regression":
            base_prompt += f"""
Step '{metadata.get('step_name', '')}' regressed {metadata.get('regression_percent', 0):.1f}%.
What could cause this specific step to slow down?
"""
        elif diagnostic_type == "resource_waste":
            base_prompt += f"""
Resource limits are {metadata.get('waste_ratio', 0):.1f}× higher than actual usage.
What's the best way to optimize this?
"""
        elif diagnostic_type == "pattern_match":
            base_prompt += f"""
This failure pattern has been seen {len(metadata.get('matches', []))} times.
What's the likely root cause and how to prevent it?
"""
        
        return base_prompt
    
    def _query_huggingface(self, prompt: str) -> Optional[str]:
        """Query Hugging Face Inference API (free tier)"""
        try:
            # Using a small, fast model for free inference
            model = "microsoft/DialoGPT-small"  # Free, no auth needed for small models
            # Or use: "gpt2" for text generation
            
            # For better results, use a model that supports instruction following
            # But requires API key: "mistralai/Mistral-7B-Instruct-v0.1"
            
            url = f"https://api-inference.huggingface.co/models/{model}"
            headers = {}
            if hasattr(self, 'hf_key') and self.hf_key:
                headers["Authorization"] = f"Bearer {self.hf_key}"
            
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 100,
                    "temperature": 0.7,
                    "return_full_text": False
                }
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get("generated_text", "")
                    # Extract first sentence
                    suggestion = generated_text.split(".")[0] + "." if generated_text else None
                    return suggestion
            elif response.status_code == 503:
                # Model is loading, return None (fallback to non-AI)
                return None
            
        except Exception as e:
            print(f"AI suggestion error: {e}")
            return None
        
        return None
    
    def _query_openai(self, prompt: str) -> Optional[str]:
        """Query OpenAI API (free tier available)"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",  # Cheapest model
                messages=[
                    {"role": "system", "content": "You are a DevOps expert. Provide brief, actionable suggestions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            suggestion = response.choices[0].message.content.strip()
            return suggestion
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return None
    
    def generate_summary(self, diagnostics: list) -> str:
        """Generate AI summary of all diagnostics"""
        if not self.use_ai or len(diagnostics) == 0:
            return ""
        
        prompt = f"""Summarize these {len(diagnostics)} CI/CD diagnostics into 2-3 key priorities:
        
{chr(10).join([f"- {d.get('title', '')}: {d.get('message', '')[:100]}" for d in diagnostics[:5]])}

Provide a brief executive summary."""
        
        if self.provider == "huggingface":
            return self._query_huggingface(prompt) or ""
        elif self.provider == "openai":
            return self._query_openai(prompt) or ""
        
        return ""

