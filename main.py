import argparse
import sys
from agent.agent import BrandProtectionAgent
from agent.utils import get_api_key
from agent.logger import Logger


def main():
    parser = argparse.ArgumentParser(
        description="Brand Protection Analyst Agent - Semantic domain monitoring for any brand",
        epilog="""
        
        Data Folder:
          All input and output files are managed in the 'data/' folder.

        API Key Options:
          1. --api-key command line argument
          2. GEMINI_API_KEY environment variable  
          3. .env file with GEMINI_API_KEY=your_key
            3.1. Create .env file via CLI: echo "GEMINI_API_KEY=your_actual_api_key_here" > .env
          4. Interactive secure input (fallback)
          
        Example Commands:
          python main.py --domains tui.txt --brand-name "tui"
          python main.py --domains tui.txt --brand-name "tui" --company-name "TUI AG" --output tui_results.csv
          python main.py --domains tui.txt --brand-name "tui" --company-name "TUI AG" --industry "Travel & Tourism" --description "TUI AG (trading as TUI Group) is a German multinational leisure, travel and tourism company; it is the largest such company in the world. It fully or partially owns several travel agencies, hotel chains, cruise lines and retail shops as well as five European airlines. TUI is an acronym for Touristik Union International (Tourism Union International). It is headquartered in Hanover, Germany" --batch-size 500 --analyst junior --output tui_results.csv
        
        Analyst Modes:
          - junior: Entry-level analyst - Follows established patterns, consistent threat detection (deterministic evaluations)
          - senior: Experienced analyst - Balanced expertise with nuanced reasoning (slightly creative evaluations)  
          - expert: Specialist - Advanced pattern recognition and novel threat detection (more creative evaluations)
        
        Gemini Model Information:
            rate limit: https://ai.google.dev/gemini-api/docs/rate-limits?hl=de
            doc: https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-pro

        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--domains', required=True, help='Required: To be analyzed domain filename in data/ folder (e.g., "tui.txt")')
    parser.add_argument('--brand-name', required=True, help='Required: Brand name for analysis (e.g., "tui", "otto", "nike", "gea")')

    parser.add_argument('--api-key',  help='Optional: Gemini API key (alternative to environment variable or .env file)')
    parser.add_argument('--company-name', help='Optional: Full company name (e.g., "TUI AG", "Otto GmbH & Co. KGaA")')
    parser.add_argument('--industry', help='Optional: Industry/business sector (e.g., "Travel & Tourism", "Technology")')
    parser.add_argument('--description', help='Optional: Brand / Company / Business related description (helps improve analysis accuracy by context understanding)')
    parser.add_argument('--batch-size', type=int, default=200, help='Optional: Number of domains to process per API request (default: 200)')
    parser.add_argument('--output', help='Optional: Output filename in data/ folder (e.g., "tui_results.csv")')
    parser.add_argument('--analyst', choices=['junior', 'senior', 'expert'], default='senior', help='Optional: Analyst experience level: junior (consistent, follows established patterns), senior (balanced expertise), expert (sophisticated threat detection); (default analyst: senior)')

    args = parser.parse_args()

    if not args.domains:
        parser.print_help()
        Logger.trace_warning_info("Error: --domains command is required")
        sys.exit(1)

    if not args.brand_name:
        parser.print_help()
        Logger.trace_warning_info("Error: --brand-name command is required")
        sys.exit(1)

    try:
        api_key = get_api_key(args)
        if not api_key:
            Logger.trace_warning_info("No API key provided. Cannot proceed.")
            sys.exit(1)

        agent = BrandProtectionAgent(analyst_mode=args.analyst, api_key=api_key)

        results = agent.analyze_domains(
            domains_file=args.domains,
            brand_name=args.brand_name,
            company_name=args.company_name,
            industry=args.industry,
            description=args.description,
            batch_size=args.batch_size,
            output_path=args.output
        )

        if results and results.metadata:
            metadata = results.metadata
            Logger.trace_info(f"\n=== ANALYSIS SUMMARY ===")
            Logger.trace_info(f"Brand: {metadata.brand}")
            Logger.trace_info(f"Total domains: {metadata.total_domains}")
            Logger.trace_info(f"Threats found: {metadata.threat_count}")
            Logger.trace_info(f"Filtered out: {metadata.filtered_count}")
            Logger.trace_info(f"False positive reduction: {metadata.false_positive_reduction}")
            Logger.trace_info(f"Analysis completed in {args.analyst.upper()} mode")

            if metadata.threat_count > 0:
                Logger.trace_info(f"\n{metadata.threat_count} domains require investigation:")
                for threat in results.threats:
                    Logger.trace_info(f"{threat.domain} ({threat.risk_level}) - ({threat.reason})")

            else:
                Logger.trace_info("No threats detected!")

    except Exception as e:
        Logger.trace_exception(e, additional_info="Unexpected Error occured")
        sys.exit(1)


if __name__ == "__main__":
    main()
