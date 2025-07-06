def create_evaluation_prompt(domains: list[str], brand_config: dict) -> str:
    context_notes = '\n'.join([f"- {note}" for note in brand_config['context_notes']])

    prompt = f"""You are a Brand Protection Analyst for {brand_config['name']} ({brand_config['industry']}) for several years now.

    BRAND CONTEXT:
    - Company: {brand_config['name']}
    - Industry: {brand_config['industry']}
    - Description: {brand_config['description']}

    CONTEXT NOTES:
    {context_notes}

    TASK: Analyze these newly registered domains for potential brand threats. Only return domains that could realistically threaten {brand_config['name']} through customer confusion or impersonation.

    DOMAINS TO CHECK:
    """

    for i, domain in enumerate(domains, 1):
        prompt += f"{i}. {domain}\n"

    prompt += f"""

    CRITICAL THREAT ASSESSMENT RULES:
    1. Domains that combine the brand name with legitimate business terms (com, corp, group, tech, solutions, services, global, etc.) are HIGH RISK - they appear credible and can confuse customers
    2. Domains that look "professional" or "official" and could confuse customers
    3. Domains that could represent official services, divisions, or products
    4. Consider: "Would a customer believe this could be an official {brand_config['name']} website or service?"
    5. The more legitimate a domain appears, the higher the threat level for customer confusion


    NEVER FLAG as threats:
    1. Brand name + random character strings
    2. Domains where suspicious TLD is the only concerning factor

    Your response should be in this exact JSON format:
    """

    prompt += """
    {
        "threats": [
            {
                "domain": "risky-domain.com",
                "reason": "Could impersonate official services",
                "risk_level": "HIGH",
                "confidence": 0.9
            }
        ]
    }

    If no domains are risky, respond with:
    {
        "threats": []
    }

    Analyze now:"""

    return prompt
