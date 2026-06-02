#include "AGSUI/AGSCommonButtonStyles.h"

static FSlateBrush MakeRoundedBrush(FLinearColor FillColor, FLinearColor OutlineColor, float Radius = 6.0f, float OutlineWidth = 1.0f)
{
	FSlateBrush Brush;
	Brush.DrawAs = ESlateBrushDrawType::RoundedBox;
	Brush.TintColor = FSlateColor(FillColor);
	Brush.OutlineSettings = FSlateBrushOutlineSettings(Radius, FSlateColor(OutlineColor), OutlineWidth);
	return Brush;
}

static const FLinearColor DisabledColor(0.2f, 0.2f, 0.2f, 0.4f);

UAGSPrimaryButtonStyle::UAGSPrimaryButtonStyle()
{
	static const FLinearColor Fill(0.043f, 0.424f, 1.0f, 1.0f);
	static const FLinearColor Hover(0.031f, 0.341f, 0.86f, 1.0f);
	static const FLinearColor Pressed(0.022f, 0.251f, 0.66f, 1.0f);

	NormalBase    = MakeRoundedBrush(Fill,    Fill);
	NormalHovered = MakeRoundedBrush(Hover,   Hover);
	NormalPressed = MakeRoundedBrush(Pressed, Pressed);
	Disabled      = MakeRoundedBrush(DisabledColor, DisabledColor, 6.0f, 0.0f);
}

UAGSSecondaryButtonStyle::UAGSSecondaryButtonStyle()
{
	static const FLinearColor Fill(1.0f, 1.0f, 1.0f, 1.0f);
	static const FLinearColor Hover(0.94f, 0.97f, 1.0f, 1.0f);
	static const FLinearColor Pressed(0.89f, 0.94f, 1.0f, 1.0f);
	static const FLinearColor Border(0.043f, 0.424f, 1.0f, 1.0f);

	NormalBase    = MakeRoundedBrush(Fill,    Border);
	NormalHovered = MakeRoundedBrush(Hover,   Border);
	NormalPressed = MakeRoundedBrush(Pressed, Border);
	Disabled      = MakeRoundedBrush(DisabledColor, DisabledColor, 6.0f, 0.0f);
}

UAGSDangerButtonStyle::UAGSDangerButtonStyle()
{
	static const FLinearColor Fill(0.89f, 0.14f, 0.2f, 1.0f);
	static const FLinearColor Hover(0.75f, 0.09f, 0.13f, 1.0f);

	NormalBase    = MakeRoundedBrush(Fill, Fill);
	NormalHovered = MakeRoundedBrush(Hover, Hover);
	NormalPressed = MakeRoundedBrush(Hover, Hover);
	Disabled      = MakeRoundedBrush(DisabledColor, DisabledColor, 6.0f, 0.0f);
}

UAGSIconButtonStyle::UAGSIconButtonStyle()
{
	static const FLinearColor Fill(1.0f, 1.0f, 1.0f, 1.0f);
	static const FLinearColor Hover(0.96f, 0.97f, 0.99f, 1.0f);
	static const FLinearColor Pressed(0.88f, 0.9f, 0.94f, 1.0f);
	static const FLinearColor Border(0.84f, 0.87f, 0.92f, 1.0f);

	NormalBase    = MakeRoundedBrush(Fill,    Border);
	NormalHovered = MakeRoundedBrush(Hover,   Border);
	NormalPressed = MakeRoundedBrush(Pressed, Border);
	Disabled      = MakeRoundedBrush(DisabledColor, DisabledColor, 6.0f, 0.0f);
}
