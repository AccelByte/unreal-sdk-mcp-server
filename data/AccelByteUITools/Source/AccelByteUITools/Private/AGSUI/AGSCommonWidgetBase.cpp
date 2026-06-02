#include "AGSUI/AGSCommonWidgetBase.h"
#include "AGSUI/AGSCommonButtonStyles.h"
#include "Components/Image.h"
#include "Engine/Texture2D.h"

void UAGSCommonButtonBase::NativePreConstruct()
{
	Super::NativePreConstruct();

	// Only apply the default style when no style has been explicitly assigned.
	if (Style == nullptr)
	{
		switch (Variant)
		{
		case EAGSButtonVariant::Secondary:
			SetStyle(UAGSSecondaryButtonStyle::StaticClass());
			break;
		case EAGSButtonVariant::Danger:
			SetStyle(UAGSDangerButtonStyle::StaticClass());
			break;
		case EAGSButtonVariant::Icon:
			SetStyle(UAGSIconButtonStyle::StaticClass());
			break;
		default:
			SetStyle(UAGSPrimaryButtonStyle::StaticClass());
			break;
		}
	}
}

void UAGSCommonButtonBase::SetLabel(const FText& InLabel)
{
	if (ButtonText)
	{
		ButtonText->SetText(InLabel);
	}
}

void UAGSCommonButtonBase::SetSelected(bool bInSelected)
{
	SetIsSelected(bInSelected);
}

void UAGSCommonButtonBase::NativeOnClicked()
{
	Super::NativeOnClicked();
	OnClicked.Broadcast();
}

void UAGSCommonIconButtonBase::SetIcon(UTexture2D* InTexture)
{
	if (ButtonIcon && InTexture)
	{
		ButtonIcon->SetBrushFromTexture(InTexture);
	}
}
