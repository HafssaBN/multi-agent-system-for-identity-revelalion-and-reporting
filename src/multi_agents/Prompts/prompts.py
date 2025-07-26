AIRBNB_ANALYZER_PROMPT = """
You are an expert at analyzing Airbnb host profiles. Analyze the provided host information and extract key details that could help identify this person on social media platforms.

Host Name: {host_name}
Host Bio: {host_bio}
Host Details: {host_details}
Sample Listings: {listings_info}
Sample Reviews: {reviews_sample}

Focus on extracting:
1. Identifying information (name variations, nicknames)
2. Location information (cities, neighborhoods, countries)
3. Interests and hobbies mentioned
4. Business or professional information
5. Unique characteristics or specialties

Provide a structured analysis of the host's identity markers.
"""

KEYWORD_EXTRACTOR_PROMPT = """
Based on the Airbnb host information, generate search keywords for finding this person on Instagram.

Host Name: {host_name}
Host Bio: {host_bio}
Host Details: {host_details}
Listings: {listings_info}
Reviews: {reviews_sample}
User Query: {user_query}

Generate two types of keywords:

SEARCH_KEYWORDS:
- Possible usernames (name variations, with/without spaces, with numbers)
- Business names mentioned
- Unique identifiers
- Professional titles or roles

LOCATION_KEYWORDS:
- Cities and neighborhoods mentioned
- Country-specific terms
- Local landmarks or areas
- Regional identifiers

Format your response exactly as shown above with the section headers.
"""

INSTAGRAM_SEARCHER_PROMPT = """
You are searching Instagram for profiles that might match an Airbnb host.

Search Strategy:
1. Try exact name matches
2. Try name variations (with/without spaces, numbers)
3. Try business-related usernames
4. Try location-based combinations
5. Try profession-related terms

Focus on finding profiles that could reasonably belong to someone who hosts on Airbnb.
"""

PROFILE_MATCHER_PROMPT = """
Analyze if this Instagram profile could belong to the Airbnb host. Provide a confidence score and reasoning.

AIRBNB HOST:
Name: {airbnb_name}
Bio: {airbnb_bio}
Details: {airbnb_details}
Listings: {airbnb_listings}

INSTAGRAM PROFILE:
Username: {instagram_username}
Name: {instagram_name}
Bio: {instagram_bio}
Followers: {instagram_followers}
Verified: {instagram_verified}
Recent Posts: {instagram_posts}

Analyze for matches in:
1. Name similarity
2. Location mentions
3. Hosting/travel content
4. Business activities
5. Lifestyle indicators
6. Timeline consistency

Provide your response in this format:
CONFIDENCE_SCORE: [0-100]
MATCH_REASONS:
- Reason 1
- Reason 2
- Reason 3

Be thorough but conservative in your matching.
"""

REPORT_GENERATOR_PROMPT = """
Generate a comprehensive report about the Instagram profiles found for the Airbnb host search.

User Query: {user_query}
Airbnb Host: {airbnb_host_name}
Airbnb Profile: {airbnb_profile_url}
Total Profiles Found: {total_profiles_found}
High Confidence Matches: {high_confidence_count}
Top Profiles: {top_profiles}

Create a detailed report that includes:
1. Executive summary of the search
2. Analysis methodology used
3. Key findings and confidence levels
4. Top matches with explanations
5. Limitations and caveats
6. Recommendations for further investigation

Make the report professional and actionable for identity verification purposes.
"""