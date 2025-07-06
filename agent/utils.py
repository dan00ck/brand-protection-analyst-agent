import sys
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import csv
from dotenv import load_dotenv
from agent.models import BrandAnalysisResult, ThreatAnalysis, AnalysisMetadata
from agent.logger import Logger


class ResultsProcessor:
    @staticmethod
    def process_results(domains: list[str], llm_results: dict[str, dict], brand_config: dict, batch_size: int) -> BrandAnalysisResult:
        timestamp = datetime.now().isoformat()
        threats = []
        filtered = []

        for domain in domains:
            result = llm_results.get(domain, {
                'relevant': True,
                'confidence': 0.5,
                'reason': 'LLM evaluation unavailable',
                'risk_level': 'medium'
            })

            threat_analysis = ThreatAnalysis(
                domain=domain,
                is_threat=result.get('relevant', True),
                confidence=result.get('confidence', 0.5),
                reason=result.get('reason', ''),
                risk_level=result.get('risk_level', 'medium'),
                timestamp=timestamp
            )

            if threat_analysis.is_threat:
                threats.append(threat_analysis)
            else:
                filtered.append(threat_analysis)

        metadata = AnalysisMetadata(
            brand=brand_config['name'],
            keyword=brand_config['name'].lower(),
            total_domains=len(domains),
            threat_count=len(threats),
            filtered_count=len(filtered),
            false_positive_reduction=f"{len(filtered) / len(domains) * 100:.1f}%" if domains else "0.0%",
            timestamp=timestamp,
            batch_size=batch_size
        )

        return BrandAnalysisResult(
            metadata=metadata,
            threats=threats,
            filtered=filtered
        )

    @staticmethod
    def save_results(results: BrandAnalysisResult, output_path: str):
        # Ensure data folder exists
        Path("data").mkdir(exist_ok=True)

        if not output_path.startswith("data/") and not output_path.startswith("data\\"):
            base_name = output_path.replace('.csv', '').replace('.json', '')
            output_base_path = os.path.join("data", base_name)
        else:
            output_base_path = os.path.splitext(output_path)[0]

        # Ensure the directory exists
        Path(output_base_path).parent.mkdir(parents=True, exist_ok=True)

        saved_files = []

        if results.threats:
            threats_csv_path = f"{output_base_path}_threats.csv"
            with open(threats_csv_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['domain', 'is_threat', 'confidence', 'reason', 'risk_level', 'timestamp']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows([threat.to_dict() for threat in results.threats])
            Logger.trace_info(f"Threats saved to {threats_csv_path}")
            saved_files.append(threats_csv_path)

        if results.filtered:
            filtered_csv_path = f"{output_base_path}_filtered.csv"
            with open(filtered_csv_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['domain', 'is_threat', 'confidence', 'reason', 'risk_level', 'timestamp']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows([filtered.to_dict() for filtered in results.filtered])
            Logger.trace_info(f"Filtered domains saved to {filtered_csv_path}")
            saved_files.append(filtered_csv_path)

        # Save complete results to JSON
        json_path = f"{output_base_path}_complete.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results.to_dict(), f, indent=2, ensure_ascii=False)
        Logger.trace_info(f"Complete results saved to {json_path}")
        saved_files.append(json_path)

        Logger.trace_info(f"All results saved to data/ folder:")
        for file_path in saved_files:
            Logger.trace_info(f"  - {os.path.basename(file_path)}")


class DomainLoader:
    @staticmethod
    def load_domains(file_path: str) -> list[str]:
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    domains = [line.strip().lower() for line in f if line.strip()]
                Logger.trace_info(f"Loaded {len(domains)} domains from {file_path}")
                return domains
            except Exception as e:
                Logger.trace_exception(e, additional_info=f"Error loading domains from {file_path}")
                raise

        data_path = os.path.join("data", os.path.basename(file_path))
        if os.path.isfile(data_path):
            try:
                with open(data_path, 'r', encoding='utf-8') as f:
                    domains = [line.strip().lower() for line in f if line.strip()]
                Logger.trace_info(f"Loaded {len(domains)} domains from {data_path}")
                return domains
            except Exception as e:
                Logger.trace_exception(e, additional_info=f"Error loading domains from {data_path}")
                raise

        raise FileNotFoundError(f"Domain file not found: {file_path} (also tried data/{os.path.basename(file_path)})")

    @staticmethod
    def filter_full_word_matches(domains: list[str], keyword: str) -> list[str]:
        keyword_lower = keyword.lower()
        matches = []
        for domain in domains:
            if keyword_lower in domain:
                matches.append(domain)

        Logger.trace_info(f"Found {len(matches)} domains with full word '{keyword}' matches")
        return matches


class BrandProtectionConfig:
    def get_brand_config(self, brand_name: str = None, company_name: str = None, industry: str = None, description: str = None) -> Optional[dict]:
        if brand_name:
            return self._create_dynamic_brand_config(brand_name, company_name, industry, description)

        return None

    @staticmethod
    def _create_dynamic_brand_config(brand_name: str, company_name: str = None, industry: str = None, description: str = None) -> dict:
        industry = industry or "Business"
        description = description or f"{company_name} is a company that users want to protect from domain impersonation and cybersquatting."
        company_name = company_name or brand_name

        return {
            'name': company_name.upper(),
            'industry': industry,
            'description': description,
            'context_notes': [
                f'Focus on domains that could confuse customers of {company_name}',
                f'Consider domains that impersonate {brand_name} services',
                f'Filter out domains where "{brand_name.lower()}" appears coincidentally',
                'Evaluate based on business context and customer confusion potential'
            ]
        }


def get_api_key(args) -> Optional[str]:
    """
    Get API key from multiple sources with priority order:
    1. Command line argument (--api-key)
    2. Environment variable (GEMINI_API_KEY)
    3. .env file
    4. Interactive input (secure)
    """

    # 1. Command line argument
    if args.api_key:
        Logger.trace_info("Using API key from command line argument")
        return args.api_key

    # 2. Environment variable
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        Logger.trace_info("Using API key from GEMINI_API_KEY environment variable")
        return api_key

    # 3. .env file
    try:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            return api_key
    except ImportError:
        pass

    # 4. Interactive input
    Logger.trace_warning_info("No API key found in arguments, environment, or .env file")
    Logger.trace_info("\nGemini API Key Required")
    Logger.trace_info("Get your free API key at: https://aistudio.google.com/app/apikey")
    Logger.trace_info("Enter your API key (input will be hidden for security):")

    try:
        import getpass
        api_key = getpass.getpass("API Key: ").strip()
        if api_key:
            Logger.trace_info("Using API key from interactive input")
            # Temporarily set environment variable for this session
            os.environ["GEMINI_API_KEY"] = api_key
            return api_key.strip()
        else:
            raise ValueError("No API key provided")
    except (KeyboardInterrupt, EOFError) as e:
        Logger.trace_exception(e, additional_info="Operation cancelled by user")
        sys.exit(1)
