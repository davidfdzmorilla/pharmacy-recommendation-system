"""
System prompt builder and response parser for Claude API.
Generates contextual prompts for pharmacy recommendations.
"""
import json
import re
from typing import List, Dict, Optional
from raspberry_app.utils.logger import LoggerMixin


class PromptBuilder(LoggerMixin):
    """
    Builds prompts for Claude API and parses responses.

    Handles:
    - System prompt configuration
    - Cart context formatting
    - JSON response parsing (clean and embedded)
    """

    # System prompt for Claude API
    SYSTEM_PROMPT = """Eres un farmacéutico experto especializado en recomendaciones de productos farmacéuticos en España.

Tu rol es analizar el carrito de compra del cliente y sugerir 3-5 productos complementarios que sean:
1. Terapéuticamente relevantes para los productos ya seleccionados
2. Seguros y apropiados para uso conjunto
3. Comúnmente recomendados en farmacias españolas

REGLAS IMPORTANTES:
- NO recomiendes productos de la misma categoría que ya están en el carrito
- NO recomiendes productos con el mismo principio activo
- Prioriza combinaciones seguras y efectivas
- Considera efectos secundarios y contraindicaciones
- Enfoca en prevención y cuidado complementario

EJEMPLOS DE RECOMENDACIONES APROPIADAS:
- Con antiinflamatorios (AINE): Protectores gástricos (omeprazol)
- Con antibióticos: Probióticos para flora intestinal
- Con analgésicos: Vitaminas del grupo B para neuropatía
- Con antihistamínicos: Hidratante nasal o colirios
- Con antidiarreicos: Suero oral rehidratante

FORMATO DE RESPUESTA:
Debes responder ÚNICAMENTE con un objeto JSON válido con esta estructura:

{
  "recommendations": [
    {
      "product_name": "Nombre exacto del producto",
      "category": "Categoría del producto",
      "reason": "Explicación breve (máx 80 caracteres) de por qué se recomienda",
      "priority": "high|medium|low",
      "estimated_price": "Precio estimado en euros (formato: '12.50')"
    }
  ],
  "analysis": "Análisis breve del carrito y razón general de las recomendaciones"
}

PRIORIDADES:
- high: Recomendación crítica (ej: protector gástrico con AINE)
- medium: Recomendación beneficiosa (ej: vitaminas con antibióticos)
- low: Recomendación opcional (ej: complementos generales)

NO incluyas markdown, explicaciones adicionales, ni texto fuera del JSON.
"""

    @staticmethod
    def build_recommendation_prompt(cart_items: List[Dict]) -> str:
        """
        Build user prompt with cart context.

        Args:
            cart_items: List of products in cart, each with:
                - name: Product name
                - category: Product category
                - active_ingredient: Active ingredient
                - price: Product price

        Returns:
            Formatted prompt string for Claude

        Example:
            >>> items = [
            ...     {"name": "Ibuprofeno 600mg", "category": "Analgésicos",
            ...      "active_ingredient": "Ibuprofeno", "price": 4.95}
            ... ]
            >>> prompt = PromptBuilder.build_recommendation_prompt(items)
        """
        if not cart_items:
            return "El carrito está vacío. No puedo generar recomendaciones sin productos."

        # Build structured cart summary
        cart_summary = []
        categories = set()
        active_ingredients = set()

        for idx, item in enumerate(cart_items, 1):
            name = item.get('name', 'Producto desconocido')
            category = item.get('category', 'Sin categoría')
            ingredient = item.get('active_ingredient', 'No especificado')
            price = item.get('price', 0.0)

            categories.add(category)
            active_ingredients.add(ingredient)

            cart_summary.append(
                f"{idx}. {name}\n"
                f"   - Categoría: {category}\n"
                f"   - Principio activo: {ingredient}\n"
                f"   - Precio: €{price:.2f}"
            )

        # Format prompt
        prompt = f"""Analiza el siguiente carrito de compra y genera recomendaciones:

CARRITO ACTUAL:
{chr(10).join(cart_summary)}

RESUMEN:
- Total de productos: {len(cart_items)}
- Categorías presentes: {', '.join(sorted(categories))}
- Principios activos: {', '.join(sorted(active_ingredients))}

Por favor, genera 3-5 recomendaciones de productos complementarios siguiendo las reglas establecidas.
Recuerda responder SOLO con el objeto JSON, sin texto adicional."""

        return prompt

    @staticmethod
    def parse_recommendations(response_text: str) -> Optional[Dict]:
        """
        Parse JSON response from Claude.
        Handles both clean JSON and JSON embedded in text.

        Args:
            response_text: Raw response from Claude API

        Returns:
            Parsed dict with "recommendations" and "analysis" keys,
            or None if parsing fails

        Example:
            >>> response = '{"recommendations": [...], "analysis": "..."}'
            >>> result = PromptBuilder.parse_recommendations(response)
            >>> result["recommendations"]
            [...]
        """
        logger = PromptBuilder().logger

        if not response_text or not response_text.strip():
            logger.error("Empty response text")
            return None

        # Try to parse as clean JSON first
        try:
            data = json.loads(response_text.strip())
            if "recommendations" in data:
                logger.info("Successfully parsed clean JSON response")
                return data
        except json.JSONDecodeError:
            logger.debug("Response is not clean JSON, trying to extract JSON from text")

        # Try to extract JSON from markdown code blocks
        # Pattern: ```json\n{...}\n```
        json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_block_pattern, response_text, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                if "recommendations" in data:
                    logger.info("Successfully extracted JSON from markdown block")
                    return data
            except json.JSONDecodeError:
                continue

        # Try to find JSON object directly in text
        # Pattern: {...} with proper nesting
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, response_text, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                if "recommendations" in data:
                    logger.info("Successfully extracted JSON from text")
                    return data
            except json.JSONDecodeError:
                continue

        # If all parsing attempts fail
        logger.error(f"Failed to parse JSON from response: {response_text[:200]}...")
        return None

    @staticmethod
    def validate_recommendations(data: Dict) -> bool:
        """
        Validate parsed recommendations structure.

        Args:
            data: Parsed JSON dict

        Returns:
            True if valid, False otherwise
        """
        logger = PromptBuilder().logger

        # Check required top-level keys
        if "recommendations" not in data:
            logger.error("Missing 'recommendations' key")
            return False

        recommendations = data["recommendations"]

        # Check recommendations is a list
        if not isinstance(recommendations, list):
            logger.error("'recommendations' is not a list")
            return False

        # Check we have at least one recommendation
        if len(recommendations) == 0:
            logger.warning("Empty recommendations list")
            return False

        # Validate each recommendation
        required_fields = ["product_name", "category", "reason", "priority"]
        valid_priorities = ["high", "medium", "low"]

        for idx, rec in enumerate(recommendations):
            # Check required fields
            for field in required_fields:
                if field not in rec:
                    logger.error(f"Recommendation {idx} missing field: {field}")
                    return False

            # Validate priority
            if rec["priority"] not in valid_priorities:
                logger.error(f"Recommendation {idx} has invalid priority: {rec['priority']}")
                return False

        logger.info(f"Validated {len(recommendations)} recommendations")
        return True


# Example usage
if __name__ == "__main__":
    # Test prompt building
    sample_cart = [
        {
            "name": "Ibuprofeno 600mg 20 comprimidos",
            "category": "Analgésicos",
            "active_ingredient": "Ibuprofeno",
            "price": 4.95
        },
        {
            "name": "Paracetamol 1g 40 comprimidos",
            "category": "Analgésicos",
            "active_ingredient": "Paracetamol",
            "price": 3.50
        }
    ]

    builder = PromptBuilder()

    print("=" * 60)
    print("TESTING PROMPT BUILDER")
    print("=" * 60)

    # Build prompt
    prompt = builder.build_recommendation_prompt(sample_cart)
    print("\nGENERATED PROMPT:")
    print(prompt)

    # Test JSON parsing
    print("\n" + "=" * 60)
    print("TESTING JSON PARSING")
    print("=" * 60)

    # Test 1: Clean JSON
    clean_json = '''
    {
        "recommendations": [
            {
                "product_name": "Omeprazol 20mg",
                "category": "Digestivos",
                "reason": "Protección gástrica con antiinflamatorios",
                "priority": "high",
                "estimated_price": "8.50"
            }
        ],
        "analysis": "Carrito con analgésicos, recomiendo protector gástrico"
    }
    '''

    result = builder.parse_recommendations(clean_json)
    print(f"\nClean JSON: {'✅ Parsed' if result else '❌ Failed'}")
    if result:
        print(f"  - Recommendations: {len(result['recommendations'])}")
        print(f"  - Valid: {'✅' if builder.validate_recommendations(result) else '❌'}")

    # Test 2: JSON in markdown
    markdown_json = '''
    Aquí están mis recomendaciones:

    ```json
    {
        "recommendations": [
            {
                "product_name": "Probióticos",
                "category": "Digestivos",
                "reason": "Flora intestinal",
                "priority": "medium",
                "estimated_price": "12.95"
            }
        ],
        "analysis": "Productos complementarios"
    }
    ```
    '''

    result = builder.parse_recommendations(markdown_json)
    print(f"\nMarkdown JSON: {'✅ Parsed' if result else '❌ Failed'}")
    if result:
        print(f"  - Recommendations: {len(result['recommendations'])}")
        print(f"  - Valid: {'✅' if builder.validate_recommendations(result) else '❌'}")

    print("\n✅ PromptBuilder testing complete")
