#include "AGSUI/AGSWidgetBase.h"
#include "Blueprint/WidgetTree.h"

#include "Components/Button.h"
#include "Styling/SlateTypes.h"
#include "Components/EditableTextBox.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Components/Widget.h"
#include "Components/WidgetSwitcher.h"
#include "Engine/Texture2D.h"

void UAGSWidgetBase::SetDisabled(const bool bInDisabled)
{
	bIsDisabled = bInDisabled;
	SetIsEnabled(!bIsDisabled);
}

void UAGSStateWidgetBase::NativeOnInitialized()
{
	Super::NativeOnInitialized();
	UpdateStateVisibility();
}

void UAGSStateWidgetBase::SetLoading(const bool bInLoading)
{
	bIsLoading = bInLoading;
	SetState(bIsLoading ? EAGSUIState::Loading : EAGSUIState::Success);
}

void UAGSStateWidgetBase::SetState(const EAGSUIState InState)
{
	CurrentState = InState;
	bIsLoading = CurrentState == EAGSUIState::Loading;
	UpdateStateVisibility();
}

void UAGSStateWidgetBase::UpdateStateVisibility()
{
	if (StateSwitcher)
	{
		StateSwitcher->SetActiveWidgetIndex(static_cast<int32>(CurrentState));
		return;
	}

	auto SetPanelVisibility = [this](UWidget* Panel, const EAGSUIState PanelState)
	{
		if (Panel)
		{
			Panel->SetVisibility(CurrentState == PanelState ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
		}
	};

	SetPanelVisibility(IdlePanel, EAGSUIState::Idle);
	SetPanelVisibility(LoadingPanel, EAGSUIState::Loading);
	SetPanelVisibility(SuccessPanel, EAGSUIState::Success);
	SetPanelVisibility(EmptyPanel, EAGSUIState::Empty);
	SetPanelVisibility(ErrorPanel, EAGSUIState::Error);
}

void UAGSLabelValueWidgetBase::SetLabel(const FText& InLabel)
{
	if (LabelText)
	{
		LabelText->SetText(InLabel);
	}
}

void UAGSLabelValueWidgetBase::SetValue(const FText& InValue)
{
	if (ValueText)
	{
		ValueText->SetText(InValue);
	}
}

void UAGSLabelValueWidgetBase::NativeOnListItemObjectSet(UObject* InListItemObject)
{
	ListItemObject = InListItemObject;
}

void UAGSButtonBase::SetLabel(const FText& InLabel)
{
	if (ButtonText)
	{
		ButtonText->SetText(InLabel);
	}
}

void UAGSButtonBase::NativeOnInitialized()
{
	Super::NativeOnInitialized();

	if (InteractiveButton)
	{
		CachedButtonStyle = InteractiveButton->GetStyle();
		InteractiveButton->OnClicked.AddDynamic(this, &UAGSButtonBase::HandleClicked);
	}
}

void UAGSButtonBase::SetSelected(const bool bSelected)
{
	bIsSelected = bSelected;
	if (!InteractiveButton) return;

	if (bSelected)
	{
		FButtonStyle Style = CachedButtonStyle;
		Style.Normal.TintColor  = FSlateColor(SelectedColor);
		Style.Hovered.TintColor = FSlateColor(SelectedColor);
		Style.Pressed.TintColor = FSlateColor(SelectedColor * 0.85f);
		InteractiveButton->SetStyle(Style);

		if (ButtonText)
		{
			if (!bTextColorCached)
			{
				CachedTextColor = ButtonText->GetColorAndOpacity();
				bTextColorCached = true;
			}
			ButtonText->SetColorAndOpacity(FSlateColor(SelectedTextColor));
		}
	}
	else
	{
		InteractiveButton->SetStyle(CachedButtonStyle);
		if (ButtonText && bTextColorCached)
			ButtonText->SetColorAndOpacity(CachedTextColor);
	}
}

void UAGSButtonBase::NativePreConstruct()
{
	Super::NativePreConstruct();

	if (ButtonText && !DefaultLabel.IsEmpty())
	{
		ButtonText->SetText(DefaultLabel);
	}
}

void UAGSButtonBase::HandleClicked()
{
	OnClicked.Broadcast();
}

void UAGSTextInputBase::NativeOnInitialized()
{
	Super::NativeOnInitialized();

	if (SubmitButton)
	{
		SubmitButton->OnClicked.AddDynamic(this, &UAGSTextInputBase::HandleSubmitClicked);
	}
}

void UAGSTextInputBase::NativePreConstruct()
{
	Super::NativePreConstruct();

	if (ValueInput && !DefaultHintText.IsEmpty())
	{
		ValueInput->SetHintText(DefaultHintText);
	}
}

void UAGSTextInputBase::SetLabel(const FText& InLabel)
{
	if (LabelText)
	{
		LabelText->SetText(InLabel);
	}
}

void UAGSTextInputBase::SetValue(const FText& InValue)
{
	if (ValueInput)
	{
		ValueInput->SetText(InValue);
	}
}

void UAGSTextInputBase::HandleSubmitClicked()
{
	OnSubmit.Broadcast(ValueInput ? ValueInput->GetText().ToString() : FString());
}

void UAGSStatusMessageBase::SetStatus(const EAGSStatusType InStatusType, const FText& InMessage)
{
	StatusType = InStatusType;
	SetValue(InMessage);
}

void UAGSStatusMessageBase::SetError(const FText& InMessage)
{
	StatusType = EAGSStatusType::Error;
	SetValue(InMessage);
}

void UAGSActionPanelBase::NativeOnInitialized()
{
	Super::NativeOnInitialized();

	if (ConfirmButton)
	{
		ConfirmButton->OnClicked.AddDynamic(this, &UAGSActionPanelBase::HandleConfirmClicked);
	}
	if (CancelButton)
	{
		CancelButton->OnClicked.AddDynamic(this, &UAGSActionPanelBase::HandleCancelClicked);
	}
	if (RetryButton)
	{
		RetryButton->OnClicked.AddDynamic(this, &UAGSActionPanelBase::HandleRetryClicked);
	}
}

void UAGSActionPanelBase::HandleConfirmClicked()
{
	OnConfirm.Broadcast();
}

void UAGSActionPanelBase::HandleCancelClicked()
{
	OnCancel.Broadcast();
}

void UAGSActionPanelBase::HandleRetryClicked()
{
	OnRetry.Broadcast();
}

void UAGSFeatureBlockBase::NativeOnListItemObjectSet(UObject* InListItemObject)
{
	ListItemObject = InListItemObject;
}

void UAGSAvatarBase::SetAvatarImage(UTexture2D* InTexture)
{
	if (AvatarImage && InTexture)
	{
		AvatarImage->SetBrushFromTexture(InTexture);
	}
}

void UAGSIconButtonBase::SetIcon(UTexture2D* InTexture)
{
	if (ButtonIcon && InTexture)
	{
		ButtonIcon->SetBrushFromTexture(InTexture);
	}
}

void UAGSLoadingIndicatorBase::SetStatusText(const FText& InText)
{
	if (StatusText)
	{
		StatusText->SetText(InText);
	}
}

void UAGSEmptyStateBase::SetLabel(const FText& InText)
{
	if (LabelText)
	{
		LabelText->SetText(InText);
	}
}

void UAGSEmptyStateBase::SetStatusText(const FText& InText)
{
	if (StatusText)
	{
		StatusText->SetText(InText);
	}
}

void UAGSErrorStateBase::SetLabel(const FText& InText)
{
	if (LabelText)
	{
		LabelText->SetText(InText);
	}
}

void UAGSErrorStateBase::SetStatusText(const FText& InText)
{
	if (StatusText)
	{
		StatusText->SetText(InText);
	}
}

void UAGSBasePanelBase::SetLabel(const FText& InText)
{
	if (LabelText)
	{
		LabelText->SetText(InText);
	}
}

UWidget* UAGSCommonActivatableBase::NativeGetDesiredFocusTarget() const
{
	if (!WidgetTree)
	{
		return nullptr;
	}

	// Check stable widget names in priority order (matches the skill spec's stable names).
	static const TArray<FName> PriorityNames = {
		TEXT("SubmitButton"),
		TEXT("ConfirmButton"),
		TEXT("ValueInput"),
		TEXT("CancelButton"),
		TEXT("RetryButton"),
	};
	for (const FName& Name : PriorityNames)
	{
		if (UWidget* Found = WidgetTree->FindWidget(Name))
		{
			return Found;
		}
	}

	// Fall back to the first interactive widget in tree order.
	UWidget* FirstInteractive = nullptr;
	WidgetTree->ForEachWidget([&FirstInteractive](UWidget* Widget)
	{
		if (!FirstInteractive &&
			(Widget->IsA<UButton>() || Widget->IsA<UEditableTextBox>()))
		{
			FirstInteractive = Widget;
		}
	});
	return FirstInteractive;
}
