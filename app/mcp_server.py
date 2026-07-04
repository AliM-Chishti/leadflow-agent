# pyrefly: ignore [missing-import]
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("LeadFlow-MCP-Server")

# Tool 1: fetch_company_details
@mcp.tool()
def fetch_company_details(company_name: str) -> str:
    """Retrieve detailed firmographic data for a given company name.
    
    Args:
        company_name: The name of the company to look up.
    """
    company_lower = company_name.lower()
    
    # Mock Database
    db = {
        "google": {
            "name": "Google LLC",
            "domain": "google.com",
            "revenue": 307000000000.0,
            "employee_count": 182000,
            "industry": "Technology",
            "description": "Multinational technology company specializing in search engine technology, online advertising, cloud computing, and AI."
        },
        "stripe": {
            "name": "Stripe Inc.",
            "domain": "stripe.com",
            "revenue": 14000000000.0,
            "employee_count": 8000,
            "industry": "Financial Services",
            "description": "Financial infrastructure platform for the internet, providing payment-processing software and application programming interfaces."
        },
        "acme": {
            "name": "Acme Corporation",
            "domain": "acme.corp",
            "revenue": 4500000.0,
            "employee_count": 45,
            "industry": "Manufacturing",
            "description": "Global provider of cartoon gadgets, anvils, and roadrunner traps."
        },
        "ecostart": {
            "name": "EcoStart",
            "domain": "ecostart.io",
            "revenue": 500000.0,
            "employee_count": 6,
            "industry": "Environmental Services",
            "description": "Boutique environmental consulting firm specializing in local green initiatives and small-scale solar installations."
        }
    }
    
    # Simple matching logic
    for key, data in db.items():
        if key in company_lower or company_lower in key:
            import json
            return json.dumps(data)
            
    # Default mock result if not found
    default_data = {
        "name": company_name,
        "domain": f"{company_name.lower().replace(' ', '')}.com",
        "revenue": 2000000.0,
        "employee_count": 15,
        "industry": "General Business",
        "description": f"A company named {company_name} operating in general services."
    }
    import json
    return json.dumps(default_data)

# Tool 2: get_industry_benchmark
@mcp.tool()
def get_industry_benchmark(industry: str) -> str:
    """Retrieve B2B industry market benchmark statistics and product fit multipliers.
    
    Args:
        industry: The industry sector (e.g. Technology, Manufacturing, Healthcare).
    """
    benchmarks = {
        "technology": {
            "growth_index": 1.25,
            "average_deal_size": 25000,
            "fit_score_multiplier": 1.5,
            "notes": "High demand for B2B software integrations. Decision makers respond well to technical capabilities."
        },
        "financial services": {
            "growth_index": 1.10,
            "average_deal_size": 45000,
            "fit_score_multiplier": 1.3,
            "notes": "Strict security and compliance requirements. Sales cycle is longer but deal sizes are larger."
        },
        "manufacturing": {
            "growth_index": 0.95,
            "average_deal_size": 15000,
            "fit_score_multiplier": 1.0,
            "notes": "Value efficiency and cost reduction. Prefer physical demonstrations and case studies."
        },
        "environmental services": {
            "growth_index": 1.15,
            "average_deal_size": 8000,
            "fit_score_multiplier": 1.1,
            "notes": "Growing market sector. Decision makers focus heavily on ROI and ESG compliance."
        }
    }
    
    ind_lower = industry.lower()
    for key, data in benchmarks.items():
        if key in ind_lower or ind_lower in key:
            import json
            return json.dumps(data)
            
    # Default benchmark if not matched
    default_benchmark = {
        "growth_index": 1.0,
        "average_deal_size": 10000,
        "fit_score_multiplier": 1.0,
        "notes": "Standard B2B sales cycle and fit profile."
    }
    import json
    return json.dumps(default_benchmark)

# Tool 3: log_crm_lead
@mcp.tool()
def log_crm_lead(company_name: str, routing_tier: str, summary: str) -> str:
    """Log the qualified lead into the simulated Sales CRM.
    
    Args:
        company_name: Name of the company.
        routing_tier: Assigned routing tier (e.g. Tier-1, Tier-2, Tier-3).
        summary: A brief summary of qualification.
    """
    import random
    import datetime
    lead_id = f"CRM-{random.randint(10000, 99999)}"
    crm_log = {
        "crm_lead_id": lead_id,
        "timestamp": str(datetime.datetime.now()),
        "company_name": company_name,
        "routing_tier": routing_tier,
        "summary": summary,
        "status": "SUCCESSFULLY_LOGGED"
    }
    import json
    return json.dumps(crm_log)

if __name__ == "__main__":
    mcp.run()
