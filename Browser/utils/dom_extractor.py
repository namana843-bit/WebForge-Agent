import json
from typing import Dict, Any, List, Optional

class DomElement:
    """Represents a simplified extracted webpage DOM element."""
    def __init__(self, tag: str, ref: Optional[str] = None, text: str = "", attributes: Optional[Dict[str, str]] = None):
        self.tag = tag.lower()
        self.ref = ref
        self.text = text.strip()
        self.attributes = attributes or {}
        self.children: List['DomElement'] = []

    def to_xml_string(self, depth: int = 0) -> str:
        """Formats the element and its children into an LLM-friendly XML structure."""
        prefix = "  " * depth
        attrs = []
        if self.ref:
            attrs.append(f"ref=\"{self.ref}\"")
        for k, v in self.attributes.items():
            attrs.append(f"{k}=\"{v}\"")
            
        attr_str = f" {' '.join(attrs)}" if attrs else ""
        
        if not self.children and not self.text:
            return f"{prefix}<{self.tag}{attr_str} />"
            
        inner_content = self.text
        if self.children:
            child_strings = [c.to_xml_string(depth + 1) for c in self.children]
            inner_content = "\n" + "\n".join(child_strings) + f"\n{prefix}"
            
        return f"{prefix}<{self.tag}{attr_str}>{inner_content}</{self.tag}>"

class DomExtractionEngine:
    """Extracts, filters, indexes, and compresses webpage DOM elements for LLM context parsing."""

    async def extract_compressed_dom(self, page) -> str:
        """Runs the fast on-page DOM collection javascript and returns the compressed string layout."""
        # Execute an optimized, single-pass DOM collector JS snippet
        js_extractor = """
        (() => {
            let refCount = 1;
            
            function isVisible(el) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return (
                    rect.width > 0 &&
                    rect.height > 0 &&
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    style.opacity !== '0'
                );
            }
            
            function processNode(node) {
                if (node.nodeType !== Node.ELEMENT_NODE) return null;
                if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'SVG', 'TEMPLATE', 'HEAD', 'META', 'LINK'].includes(node.tagName)) return null;
                if (!isVisible(node)) return null;
                
                const isInteractive = [
                    'BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA', 'OPTION'
                ].includes(node.tagName) || node.getAttribute('role') === 'button' || node.onclick;
                
                const childData = [];
                for (const child of node.childNodes) {
                    const cVal = processNode(child);
                    if (cVal) childData.push(cVal);
                }
                
                const text = node.childNodes.length === 1 && node.firstChild.nodeType === Node.TEXT_NODE ? node.firstChild.textContent.trim() : '';
                
                // Skip generic container wrapper panels that have no interesting text/substructures
                if (!isInteractive && !text && childData.length === 0) {
                    return null;
                }
                
                const elementData = {
                    tag: node.tagName.toLowerCase(),
                    text: text || '',
                    attributes: {}
                };
                
                if (isInteractive) {
                    const refId = '@e' + refCount++;
                    node.setAttribute('data-mcp-ref', refId);
                    elementData.ref = refId;
                }
                
                // Collect specific valuable attributes
                for (const attrName of ['placeholder', 'name', 'type', 'value', 'href', 'aria-label', 'role']) {
                    const val = node.getAttribute(attrName);
                    if (val) {
                        elementData.attributes[attrName] = val;
                    }
                }
                
                if (childData.length > 0) {
                    elementData.children = childData;
                }
                
                return elementData;
            }
            
            return processNode(document.body);
        })()
        """
        
        raw_tree = await page.evaluate(js_extractor)
        if not raw_tree:
            return "<body />"
            
        structured_root = self._build_element_tree(raw_tree)
        return structured_root.to_xml_string()

    def _build_element_tree(self, node_data: dict) -> DomElement:
        """Hydrates raw JS objects back into clean DomElement hierarchies."""
        elem = DomElement(
            tag=node_data.get("tag", "div"),
            ref=node_data.get("ref"),
            text=node_data.get("text", ""),
            attributes=node_data.get("attributes", {})
        )
        
        for c in node_data.get("children", []):
            elem.children.append(self._build_element_tree(c))
            
        return elem
