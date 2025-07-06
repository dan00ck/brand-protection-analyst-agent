import json
import os
import re
import time
import random
from datetime import datetime
from typing import Optional
from google import genai
from google.genai.types import GenerateContentConfig
from agent.logger import Logger
from agent.prompt import create_evaluation_prompt
from agent.utils import DomainLoader, BrandProtectionConfig, ResultsProcessor
from agent.models import BrandAnalysisResult, AnalysisMetadata


class GeminiAnalyzer:

    def __init__(self, analyst_mode: str, model: str = "gemini-2.5-pro", timeout: int = 180, api_key: str = None):
        self.model_name = model
        self.timeout = timeout
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.mode = analyst_mode

        self.total_tokens_used = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        if self.is_configured():
            self.client = genai.Client(api_key=self.api_key)
            self.generation_config = self.get_generation_config(analyst_mode)

            Logger.trace_info(f"Google GenAI client initialized with model: {self.model_name}")
            Logger.trace_info(f"Analyst mode: {analyst_mode.upper()} - {self.get_mode_description(analyst_mode)}")
        else:
            self.model = None
            Logger.trace_warning_info("GEMINI_API_KEY not found. Please set your API key.")

    def get_generation_config(self, mode: str) -> GenerateContentConfig:
        # model paramater config: https://ai.google.dev/api/generate-content#v1beta.GenerationConfig
        if mode == "junior":        # Junior Analyst: Rule-based, consistent, follows established patterns
            return GenerateContentConfig(
                temperature=0,  # Maximum determinism
                top_k=1,  # Only most probable token
                top_p=0,  # No nucleus sampling
                seed=42,  # Fixed seed
                max_output_tokens=65536,    # default value
                response_mime_type="application/json"
            )

        elif mode == "senior":      # Senior Analyst: Experienced, nuanced reasoning, balanced approach
            return GenerateContentConfig(
                temperature=0.1,  # Tiny bit of creativity
                top_k=3,  # Consider top 3 tokens
                top_p=0.1,  # Very selective nucleus sampling
                seed=42,
                max_output_tokens=65536,  # default value
                response_mime_type="application/json"
            )

        elif mode == "expert":      # Expert Analyst: Sophisticated pattern recognition, creative threat detection
            return GenerateContentConfig(
                temperature=0.2,  # Moderate creativity
                top_k=5,  # Consider top 5 tokens
                top_p=0.2,  # Broader nucleus sampling
                seed=42,
                max_output_tokens=65536,  # default value
                response_mime_type="application/json"
            )

        else:
            Logger.trace_info(f"Unknown analyst level '{mode}', falling back to senior")
            return self.get_generation_config("senior")

    @staticmethod
    def get_mode_description(mode: str) -> str:
        descriptions = {
            "junior": "Entry-level analyst - Follows established patterns, consistent threat detection",
            "senior": "Experienced analyst - Balanced expertise with nuanced reasoning",
            "expert": "specialist - Advanced pattern recognition and novel threat detection"
        }
        return descriptions.get(mode, "Unknown analyst level")

    def is_configured(self):
        return self.api_key is not None and self.api_key.strip() != ""

    def analyze_domains(self, domains: list[str], brand_config: dict, batch_size: int) -> dict[str, dict]:
        if not self.is_configured():
            Logger.trace_warning_info("Google GenAI client not configured. Cannot analyze domains")
            return {}

        if not isinstance(batch_size, int) or batch_size <= 0:
            Logger.trace_warning_info(f"Invalid batch_size {batch_size}, using default 200")
            batch_size = 200

        results = {}
        total_batches = (len(domains) + batch_size - 1) // batch_size

        Logger.trace_info(f"Analyzing {len(domains)} domains in {total_batches} batches of {batch_size}")
        Logger.trace_info(f"Rate limits: {total_batches} requests used of 100 daily limit")

        for i in range(0, len(domains), batch_size):
            batch = domains[i:i + batch_size]
            batch_num = i // batch_size + 1

            Logger.trace_info(f"Processing batch {batch_num}/{total_batches}: {len(batch)} domains")

            max_retries = 3
            base_wait = 15

            for attempt in range(max_retries):
                try:
                    prompt = create_evaluation_prompt(batch, brand_config)
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=self.generation_config
                    )

                    if response and response.text:
                        if hasattr(response, 'usage_metadata'):
                            usage = response.usage_metadata
                            input_tokens = getattr(usage, 'prompt_token_count', 0)
                            output_tokens = getattr(usage, 'candidates_token_count', 0)
                            total_tokens = getattr(usage, 'total_token_count', 0)

                            self.total_input_tokens += input_tokens
                            self.total_output_tokens += output_tokens
                            self.total_tokens_used += total_tokens

                            Logger.trace_info(f"Token usage: Batch {batch_num}: {input_tokens} input, {output_tokens} output, {total_tokens} total")

                        batch_results = self._parse_response(response.text, batch)
                        for domain, result in batch_results.items():
                            results[domain] = result

                        break

                except Exception as e:
                    error_msg = str(e)
                    Logger.trace_warning_info(f"Error processing batch {batch_num}, attempt {attempt + 1}: {error_msg}")

                    # Check if it's a 503 overload error
                    if "503" in error_msg or "overloaded" in error_msg.lower() or "unavailable" in error_msg.lower():
                        if attempt < max_retries - 1:  # Not the last attempt
                            # Exponential backoff: 15s, 30s, 60s
                            wait_time = base_wait * (2 ** attempt) + random.uniform(0, 5)
                            Logger.trace_warning_info(f"Model overloaded. Waiting {wait_time:.1f} seconds before retry...")
                            time.sleep(wait_time)
                            continue
                        else:
                            Logger.trace_warning_info(f"Max retries reached for batch {batch_num}")
                            # Add fallback results for failed batch
                            for domain in batch:
                                results[domain] = {
                                    'domain': domain,
                                    'relevant': True,  # Conservative fallback
                                    'confidence': 0.5,
                                    'reason': f'API overloaded after {max_retries} retries',
                                    'risk_level': 'medium'
                                }
                    else:
                        # Non-503 error - add fallback and continue
                        Logger.trace_warning_info(f"Non-recoverable error for batch {batch_num}: {error_msg}")
                        for domain in batch:
                            results[domain] = {
                                'domain': domain,
                                'relevant': True,
                                'confidence': 0.5,
                                'reason': f'API error: {error_msg}',
                                'risk_level': 'medium'
                            }
                        break

            # Rate limiting between batches
            if batch_num < total_batches:
                wait_time = base_wait + random.uniform(0, 3)  # 15-18 seconds
                Logger.trace_info(f"Waiting {wait_time:.1f} seconds before next batch...")
                time.sleep(wait_time)

        Logger.trace_info(f"=== TOTAL TOKEN USAGE ===")
        Logger.trace_info(f"Input tokens: {self.total_input_tokens}")
        Logger.trace_info(f"Output tokens: {self.total_output_tokens}")
        Logger.trace_info(f"Total tokens: {self.total_tokens_used}")

        return results

    @staticmethod
    def _parse_response(response: str, batch_domains: list[str]) -> dict[str, dict]:
        try:
            # Extract JSON part from the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)

            if json_match:
                json_str = json_match.group(0)
                try:
                    data = json.loads(json_str)
                    threats = data.get('threats', [])

                    results = {}

                    # Mark all domains as not relevant first
                    for domain in batch_domains:
                        results[domain] = {
                            'domain': domain,
                            'relevant': False,
                            'confidence': 0.95,
                            'reason': 'No threat detected',
                            'risk_level': 'low'
                        }

                    # Update only the threatening domains
                    for threat in threats:
                        domain = threat.get('domain')
                        if domain in batch_domains:
                            results[domain] = {
                                'domain': domain,
                                'relevant': True,
                                'confidence': threat.get('confidence', 0.8),
                                'reason': threat.get('reason', 'Potential threat'),
                                'risk_level': threat.get('risk_level', 'medium').lower()
                            }

                    return results

                except json.JSONDecodeError as e:
                    Logger.trace_exception(e, additional_info=f"Response JSON decode error")
                    Logger.trace_debug(f"Response text: {response}")
                    return {}
            else:
                Logger.trace_warning_info("No JSON found in Gemini response")
                Logger.trace_debug(f"Response: {response}")
                return {}

        except Exception as e:
            Logger.trace_exception(e, additional_info=f"Error parsing Gemini response")
            return {}


class BrandProtectionAgent:
    def __init__(self, analyst_mode: str, api_key: str = None):
        self.analyzer = GeminiAnalyzer(api_key=api_key, analyst_mode=analyst_mode)
        self.config = BrandProtectionConfig()

    def analyze_domains(self, domains_file: str, brand_name: str = None, company_name: str = None, industry: str = None, description: str = None, output_path: Optional[str] = None, batch_size: int = 200) -> BrandAnalysisResult:
        """
        Analyze domains for a specific brand with flexible configuration

        Args:
            domains_file: Path to file containing domain names
            brand_name: Brand name for dynamic configuration
            company_name: Company name for dynamic configuration
            industry: Industry for dynamic configuration
            description: Brand description for dynamic configuration
            batch_size: Number of domains to process per API request (default: 200)
            output_path: Path to save results

        Returns:
            BrandAnalysisResult containing analysis results
        """

        if not self.analyzer.is_configured():
            raise ValueError("GEMINI_API_KEY not found. Please set your API key in environment variables or .env file.")

        # Get brand configuration
        brand_config = self.config.get_brand_config(brand_name=brand_name, company_name=company_name, industry=industry, description=description)

        if not brand_config:
            raise ValueError("No valid brand configuration provided. Use --brand-name")

        keyword = brand_name or brand_config['name'].lower()

        Logger.trace_info(f"Analyzing domains for brand: {brand_config['name']} (keyword: {keyword})")

        all_domains = DomainLoader.load_domains(domains_file)
        relevant_domains = DomainLoader.filter_full_word_matches(all_domains, keyword)

        if not relevant_domains:
            Logger.trace_warning_info(f"No domains found containing '{keyword}' as full word")

            metadata = AnalysisMetadata(
                brand=brand_config['name'],
                keyword=keyword,
                total_domains=0,
                threat_count=0,
                filtered_count=0,
                false_positive_reduction='0.0%',
                timestamp=datetime.now().isoformat(),
                batch_size=batch_size
            )

            return BrandAnalysisResult(
                metadata=metadata,
                threats=[],
                filtered=[]
            )

        llm_results = self.analyzer.analyze_domains(relevant_domains, brand_config, batch_size)

        results = ResultsProcessor.process_results(
            domains=relevant_domains,
            llm_results=llm_results,
            brand_config=brand_config,
            batch_size=batch_size
        )

        if output_path:
            ResultsProcessor.save_results(results, output_path)

        return results
