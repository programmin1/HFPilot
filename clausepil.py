from PIL import Image, ImageDraw, ImageFont
import sys

def create_colored_grid(grid_data, cell_size=100, output_file="grid_output.png"):
    """
    Create a colored grid image with numbers 0-9 in each cell.
    
    Args:
        grid_data: 2D list where each element is a dict like {'value': 5, 'color': (255, 0, 0)}
        cell_size: Size of each cell in pixels
        output_file: Output filename
    """
    rows = len(grid_data)
    cols = len(grid_data[0]) if rows > 0 else 0
    
    # Create image
    img_width = cols * cell_size
    img_height = rows * cell_size
    img = Image.new('RGB', (img_width, img_height), 'white')
    draw = ImageDraw.Draw(img)
    
    # Try to load a font, fall back to default if not available
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", cell_size // 3)
    except:
        try:
            font = ImageFont.truetype("arial.ttf", cell_size // 3)
        except:
            font = ImageFont.load_default()
    
    # Draw grid
    for row in range(rows):
        for col in range(cols):
            cell = grid_data[row][col]
            value = cell['value']
            color = cell['color']
            
            # Calculate cell position
            x1 = col * cell_size
            y1 = row * cell_size
            x2 = x1 + cell_size
            y2 = y1 + cell_size
            
            # Draw cell background
            draw.rectangle([x1, y1, x2, y2], fill=color, outline='black', width=2)
            
            # Draw text centered in cell
            text = str(value)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            text_x = x1 + (cell_size - text_width) // 2
            text_y = y1 + (cell_size - text_height) // 2
            
            # Choose text color based on background brightness
            brightness = sum(color) / 3
            text_color = 'white' if brightness < 128 else 'black'
            
            draw.text((text_x, text_y), text, fill=text_color, font=font)
    
    # Save image
    img.save(output_file)
    print(f"Grid saved to {output_file}")
    return img


# Example usage with a color scale from red (0) to green (9)
def generate_sample_grid(rows=5, cols=8):
    """Generate a sample grid with gradient colors"""
    grid_data = []
    
    # Define color gradient (0=red, 9=green)
    colors = [
        (139, 0, 0),      # 0 - Dark red
        (178, 34, 34),    # 1 - Firebrick
        (220, 20, 60),    # 2 - Crimson
        (255, 69, 0),     # 3 - Red-orange
        (255, 140, 0),    # 4 - Dark orange
        (255, 215, 0),    # 5 - Gold
        (173, 255, 47),   # 6 - Yellow-green
        (124, 252, 0),    # 7 - Lawn green
        (50, 205, 50),    # 8 - Lime green
        (0, 128, 0)       # 9 - Green
    ]
    
    for row in range(rows):
        row_data = []
        for col in range(cols):
            # Generate values 0-9 in a pattern
            value = (row + col) % 10
            color = colors[value]
            row_data.append({'value': value, 'color': color})
        grid_data.append(row_data)
    
    return grid_data


if __name__ == "__main__":
    # Generate sample grid
    grid = generate_sample_grid(rows=10, cols=12)
    
    # Create and save image
    create_colored_grid(grid, cell_size=80, output_file="signal_strength_grid.png")
    
    print("\nExample: Custom grid creation")
    print("=" * 50)
    print("# Create your own grid:")
    print("grid_data = [")
    print("    [{'value': 9, 'color': (0, 255, 0)}, {'value': 5, 'color': (255, 255, 0)}],")
    print("    [{'value': 2, 'color': (255, 0, 0)}, {'value': 7, 'color': (0, 200, 0)}]")
    print("]")
    print("create_colored_grid(grid_data, cell_size=100, output_file='my_grid.png')")
