// Copyright (c) 2026 AccelByte Inc. All Rights Reserved.
// This is licensed software from AccelByte Inc, for limitations
// and restrictions contact your company contract manager.

#include "AccelByteUIToolsLibrary.h"

#if WITH_EDITOR
#include "AGSUI/AGSWidgetBase.h"
#include "AGSUI/AGSCommonWidgetBase.h"
#include "Animation/WidgetAnimation.h"
#include "AssetToolsModule.h"
#include "Blueprint/IUserObjectListEntry.h"
#include "Blueprint/WidgetTree.h"
#include "CommonButtonBase.h"
#include "CommonTextBlock.h"
#include "Components/Border.h"
#include "Components/BorderSlot.h"
#include "Components/Button.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/ContentWidget.h"
#include "Components/EditableTextBox.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/ListViewBase.h"
#include "Components/ListView.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/PanelWidget.h"
#include "Components/SafeZone.h"
#include "Components/ScaleBox.h"
#include "Components/ScrollBox.h"
#include "Components/ScrollBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/Spacer.h"
#include "Components/TextBlock.h"
#include "Components/TileView.h"
#include "Components/TreeView.h"
#include "Components/UniformGridPanel.h"
#include "Components/UniformGridSlot.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/WidgetSwitcher.h"
#include "Components/WidgetSwitcherSlot.h"
#include "Components/WrapBox.h"
#include "Components/WrapBoxSlot.h"
#include "Dom/JsonObject.h"
#include "EditorAssetLibrary.h"
#include "Engine/Texture2D.h"
#include "Editor.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "Widgets/Layout/Anchors.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Styling/SlateBrush.h"
#include "UObject/TextProperty.h"
#include "UObject/UnrealType.h"
#include "UObject/UObjectGlobals.h"
#include "Blueprint/UserWidget.h"
#include "WidgetBlueprint.h"
#include "WidgetBlueprintFactory.h"

DEFINE_LOG_CATEGORY_STATIC(LogAccelByteUITools, Log, All);
#endif

namespace
{
#if WITH_EDITOR
// Forward declaration — defined further down in this file.
UClass* ExpectedAgsCoreWidgetClass(const FString& WidgetType, const FString& ClassPath = FString());

UClass* ResolveWidgetClass(const TSharedPtr<FJsonObject>& Node)
{
	FString ClassPath;
	if (Node.IsValid() && Node->TryGetStringField(TEXT("class_path"), ClassPath))
	{
		// Fast path: class already in the object registry (succeeds after pre-compilation).
		if (UClass* Found = LoadClass<UWidget>(nullptr, *ClassPath))
		{
			UE_LOG(LogAccelByteUITools, Verbose, TEXT("ResolveWidgetClass fast-path OK: %s -> %s"), *ClassPath, *Found->GetPathName());
			return Found;
		}

		// Fallback: force the package into memory and retry.
		int32 DotIndex;
		if (ClassPath.FindLastChar(TEXT('.'), DotIndex))
		{
			const FString AssetPath = ClassPath.Left(DotIndex);
			const FString ClassName = ClassPath.Mid(DotIndex + 1);

			UBlueprint* BP = LoadObject<UBlueprint>(nullptr, *AssetPath);
			UE_LOG(LogAccelByteUITools, Log, TEXT("ResolveWidgetClass fallback: ClassPath=%s AssetPath=%s BP=%s GenClass=%s"),
				*ClassPath, *AssetPath,
				BP ? TEXT("valid") : TEXT("NULL"),
				BP && BP->GeneratedClass ? *BP->GeneratedClass->GetPathName() : TEXT("NULL"));

			if (BP)
			{
				if (BP->GeneratedClass)
					return BP->GeneratedClass;

				if (!ClassName.IsEmpty())
				{
					if (UClass* Found = FindObject<UClass>(BP->GetOutermost(), *ClassName))
						return Found;
				}
			}

			if (UClass* Found = FindObject<UClass>(nullptr, *ClassPath))
			{
				if (Found->IsChildOf<UWidget>()) return Found;
			}

			if (UClass* Found = LoadClass<UWidget>(nullptr, *ClassPath))
			{
				return Found;
			}
		}

		// Last resort: return the AGS C++ base class so the widget is at least placed.
		FString WidgetType;
		Node->TryGetStringField(TEXT("type"), WidgetType);
		return ExpectedAgsCoreWidgetClass(WidgetType, ClassPath);
	}

	FString WidgetType;
	if (!Node.IsValid() || !Node->TryGetStringField(TEXT("type"), WidgetType))
	{
		return nullptr;
	}

	// Resolve AGS spec aliases (AGSBaseButton, AGSErrorState, etc.) using the same
	// registry used by the verifier — ensures aliases work at any nesting depth,
	// including inside generated state panel templates.
	if (UClass* AgsClass = ExpectedAgsCoreWidgetClass(WidgetType))
	{
		return AgsClass;
	}

	if (WidgetType == TEXT("CanvasPanel"))
	{
		return UCanvasPanel::StaticClass();
	}
	if (WidgetType == TEXT("Overlay"))
	{
		return UOverlay::StaticClass();
	}
	if (WidgetType == TEXT("VerticalBox"))
	{
		return UVerticalBox::StaticClass();
	}
	if (WidgetType == TEXT("HorizontalBox"))
	{
		return UHorizontalBox::StaticClass();
	}
	if (WidgetType == TEXT("SizeBox"))
	{
		return USizeBox::StaticClass();
	}
	if (WidgetType == TEXT("Border"))
	{
		return UBorder::StaticClass();
	}
	if (WidgetType == TEXT("SafeZone"))
	{
		return USafeZone::StaticClass();
	}
	if (WidgetType == TEXT("ScaleBox"))
	{
		return UScaleBox::StaticClass();
	}
	if (WidgetType == TEXT("TextBlock"))
	{
		return UTextBlock::StaticClass();
	}
	if (WidgetType == TEXT("Button"))
	{
		return UButton::StaticClass();
	}
	if (WidgetType == TEXT("EditableTextBox"))
	{
		return UEditableTextBox::StaticClass();
	}
	if (WidgetType == TEXT("Image"))
	{
		return UImage::StaticClass();
	}
	if (WidgetType == TEXT("Spacer"))
	{
		return USpacer::StaticClass();
	}
	if (WidgetType == TEXT("ScrollBox"))
	{
		return UScrollBox::StaticClass();
	}
	if (WidgetType == TEXT("ListView"))
	{
		return UListView::StaticClass();
	}
	if (WidgetType == TEXT("TileView"))
	{
		return UTileView::StaticClass();
	}
	if (WidgetType == TEXT("TreeView"))
	{
		return UTreeView::StaticClass();
	}
	if (WidgetType == TEXT("WidgetSwitcher"))
	{
		return UWidgetSwitcher::StaticClass();
	}
	if (WidgetType == TEXT("UniformGridPanel"))
	{
		return UUniformGridPanel::StaticClass();
	}
	if (WidgetType == TEXT("WrapBox"))
	{
		return UWrapBox::StaticClass();
	}
	if (WidgetType == TEXT("AccelByteWarsButtonBase"))
	{
		return LoadClass<UWidget>(nullptr, TEXT("/Script/AccelByteWars.AccelByteWarsButtonBase"));
	}
	return nullptr;
}

FVector2D ReadVector2D(const TSharedPtr<FJsonObject>& JsonObject, const FString& FieldName, const FVector2D& DefaultValue)
{
	if (!JsonObject.IsValid() || !JsonObject->HasTypedField<EJson::Array>(FieldName))
	{
		return DefaultValue;
	}

	const TArray<TSharedPtr<FJsonValue>> Values = JsonObject->GetArrayField(FieldName);
	if (Values.Num() < 2)
	{
		return DefaultValue;
	}

	return FVector2D(Values[0]->AsNumber(), Values[1]->AsNumber());
}

FAnchors ReadAnchors(const TSharedPtr<FJsonObject>& JsonObject, const FString& FieldName, const FAnchors& DefaultValue)
{
	if (!JsonObject.IsValid() || !JsonObject->HasTypedField<EJson::Array>(FieldName))
	{
		return DefaultValue;
	}

	const TArray<TSharedPtr<FJsonValue>> Values = JsonObject->GetArrayField(FieldName);
	if (Values.Num() < 4)
	{
		return DefaultValue;
	}

	return FAnchors(Values[0]->AsNumber(), Values[1]->AsNumber(), Values[2]->AsNumber(), Values[3]->AsNumber());
}

static FMargin ReadMargin(const TSharedPtr<FJsonObject>& JsonObject, const FString& FieldName, const FMargin& DefaultValue)
{
	if (!JsonObject.IsValid() || !JsonObject->HasTypedField<EJson::Array>(FieldName))
	{
		return DefaultValue;
	}

	const TArray<TSharedPtr<FJsonValue>> Values = JsonObject->GetArrayField(FieldName);
	if (Values.Num() < 4)
	{
		return DefaultValue;
	}

	return FMargin(
		static_cast<float>(Values[0]->AsNumber()),
		static_cast<float>(Values[1]->AsNumber()),
		static_cast<float>(Values[2]->AsNumber()),
		static_cast<float>(Values[3]->AsNumber())
	);
}

static bool ReadColor(const TSharedPtr<FJsonObject>& JsonObject, const FString& FieldName, FLinearColor& OutColor)
{
	if (!JsonObject.IsValid() || !JsonObject->HasTypedField<EJson::Array>(FieldName))
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>> Values = JsonObject->GetArrayField(FieldName);
	if (Values.Num() < 4)
	{
		return false;
	}

	OutColor = FLinearColor(
		static_cast<float>(Values[0]->AsNumber()),
		static_cast<float>(Values[1]->AsNumber()),
		static_cast<float>(Values[2]->AsNumber()),
		static_cast<float>(Values[3]->AsNumber())
	);
	return true;
}

static bool HasRoundedBoxStyle(const TSharedPtr<FJsonObject>& StyleObject)
{
	return StyleObject.IsValid()
		&& (StyleObject->HasField(TEXT("corner_radius"))
			|| StyleObject->HasField(TEXT("border_color"))
			|| StyleObject->HasField(TEXT("border_width")));
}

static FSlateBrush MakeRoundedBoxBrush(
	const FLinearColor& FillColor,
	const float CornerRadius,
	const FLinearColor& BorderColor,
	const float BorderWidth)
{
	FSlateBrush Brush;
	Brush.DrawAs = ESlateBrushDrawType::RoundedBox;
	Brush.TintColor = FSlateColor(FillColor);
	Brush.OutlineSettings.RoundingType = ESlateBrushRoundingType::FixedRadius;
	Brush.OutlineSettings.CornerRadii = FVector4(CornerRadius, CornerRadius, CornerRadius, CornerRadius);
	Brush.OutlineSettings.Color = BorderColor;
	Brush.OutlineSettings.Width = BorderWidth;
	return Brush;
}

static void ReadRoundedBoxStyle(
	const TSharedPtr<FJsonObject>& StyleObject,
	const FLinearColor& DefaultFillColor,
	const bool bUseColorAsFill,
	FLinearColor& OutFillColor,
	float& OutCornerRadius,
	FLinearColor& OutBorderColor,
	float& OutBorderWidth)
{
	OutFillColor = DefaultFillColor;
	ReadColor(StyleObject, TEXT("background_color"), OutFillColor);
	if (bUseColorAsFill)
	{
		ReadColor(StyleObject, TEXT("color"), OutFillColor);
	}

	OutCornerRadius = 0.0f;
	double CornerRadius = 0.0;
	if (StyleObject.IsValid() && StyleObject->TryGetNumberField(TEXT("corner_radius"), CornerRadius))
	{
		OutCornerRadius = FMath::Max(0.0f, static_cast<float>(CornerRadius));
	}

	OutBorderColor = FLinearColor::Transparent;
	ReadColor(StyleObject, TEXT("border_color"), OutBorderColor);

	OutBorderWidth = 0.0f;
	double BorderWidth = 0.0;
	if (StyleObject.IsValid() && StyleObject->TryGetNumberField(TEXT("border_width"), BorderWidth))
	{
		OutBorderWidth = FMath::Max(0.0f, static_cast<float>(BorderWidth));
	}
}

static void ApplyRoundedBoxStyleToBorder(UBorder* Border, const TSharedPtr<FJsonObject>& StyleObject)
{
	if (!Border || !HasRoundedBoxStyle(StyleObject))
	{
		return;
	}

	FLinearColor FillColor = FLinearColor::White;
	FLinearColor BorderColor = FLinearColor::Transparent;
	float CornerRadius = 0.0f;
	float BorderWidth = 0.0f;
	ReadRoundedBoxStyle(StyleObject, Border->GetBrushColor(), true, FillColor, CornerRadius, BorderColor, BorderWidth);
	Border->SetBrush(MakeRoundedBoxBrush(FillColor, CornerRadius, BorderColor, BorderWidth));
}

static void ApplyRoundedBoxStyleToButton(UButton* Button, const TSharedPtr<FJsonObject>& StyleObject)
{
	if (!Button || !HasRoundedBoxStyle(StyleObject))
	{
		return;
	}

	FLinearColor FillColor = FLinearColor::White;
	FLinearColor BorderColor = FLinearColor::Transparent;
	float CornerRadius = 0.0f;
	float BorderWidth = 0.0f;
	ReadRoundedBoxStyle(StyleObject, FLinearColor::White, true, FillColor, CornerRadius, BorderColor, BorderWidth);

	FLinearColor HoverColor = FillColor;
	ReadColor(StyleObject, TEXT("hover_color"), HoverColor);

	FLinearColor PressedColor = FillColor * 0.9f;
	PressedColor.A = FillColor.A;
	ReadColor(StyleObject, TEXT("pressed_color"), PressedColor);

	FButtonStyle ButtonStyle = Button->GetStyle();
	ButtonStyle.Normal = MakeRoundedBoxBrush(FillColor, CornerRadius, BorderColor, BorderWidth);
	ButtonStyle.Hovered = MakeRoundedBoxBrush(HoverColor, CornerRadius, BorderColor, BorderWidth);
	ButtonStyle.Pressed = MakeRoundedBoxBrush(PressedColor, CornerRadius, BorderColor, BorderWidth);
	FLinearColor DisabledColor = FillColor;
	DisabledColor.A *= 0.45f;
	ButtonStyle.Disabled = MakeRoundedBoxBrush(DisabledColor, CornerRadius, BorderColor, BorderWidth);
	Button->SetStyle(ButtonStyle);
}

static void ApplyRoundedBoxStyleToEditableTextBox(UEditableTextBox* EditableTextBox, const TSharedPtr<FJsonObject>& StyleObject)
{
	if (!EditableTextBox || !HasRoundedBoxStyle(StyleObject))
	{
		return;
	}

	FLinearColor FillColor = FLinearColor::White;
	FLinearColor BorderColor = FLinearColor::Transparent;
	float CornerRadius = 0.0f;
	float BorderWidth = 0.0f;
	ReadRoundedBoxStyle(StyleObject, FLinearColor::White, false, FillColor, CornerRadius, BorderColor, BorderWidth);

	FLinearColor HoverColor = FillColor;
	ReadColor(StyleObject, TEXT("hover_color"), HoverColor);

	EditableTextBox->WidgetStyle.BackgroundImageNormal = MakeRoundedBoxBrush(FillColor, CornerRadius, BorderColor, BorderWidth);
	EditableTextBox->WidgetStyle.BackgroundImageHovered = MakeRoundedBoxBrush(HoverColor, CornerRadius, BorderColor, BorderWidth);
	EditableTextBox->WidgetStyle.BackgroundImageFocused = MakeRoundedBoxBrush(HoverColor, CornerRadius, BorderColor, BorderWidth);
	EditableTextBox->WidgetStyle.BackgroundImageReadOnly = MakeRoundedBoxBrush(FillColor, CornerRadius, BorderColor, BorderWidth);
	EditableTextBox->WidgetStyle.SetBackgroundColor(FSlateColor(FillColor));
}

static bool ApplyCommonButtonStyle(UWidget* Widget, const TSharedPtr<FJsonObject>& Node, FString& OutError)
{
	FString StyleClassPath;
	if (!Widget || !Node.IsValid() || !Node->TryGetStringField(TEXT("button_style_class"), StyleClassPath))
	{
		return true;
	}

	UCommonButtonBase* CommonButton = Cast<UCommonButtonBase>(Widget);
	if (!CommonButton)
	{
		OutError = FString::Printf(TEXT("Widget '%s' declares button_style_class but is not a Common UI button."), *Widget->GetName());
		return false;
	}

	UClass* StyleClass = LoadClass<UCommonButtonStyle>(nullptr, *StyleClassPath);
	if (!StyleClass)
	{
		OutError = FString::Printf(TEXT("Could not load button_style_class for widget '%s': %s"), *Widget->GetName(), *StyleClassPath);
		return false;
	}

	CommonButton->SetStyle(StyleClass);
	return true;
}

static bool ApplyCommonTextStyle(UWidget* Widget, const TSharedPtr<FJsonObject>& Node, FString& OutError)
{
	FString StyleClassPath;
	if (!Widget || !Node.IsValid() || !Node->TryGetStringField(TEXT("text_style_class"), StyleClassPath))
	{
		return true;
	}

	UCommonTextBlock* CommonTextBlock = Cast<UCommonTextBlock>(Widget);
	if (!CommonTextBlock)
	{
		OutError = FString::Printf(TEXT("Widget '%s' declares text_style_class but is not a Common UI text block."), *Widget->GetName());
		return false;
	}

	UClass* StyleClass = LoadClass<UCommonTextStyle>(nullptr, *StyleClassPath);
	if (!StyleClass)
	{
		OutError = FString::Printf(TEXT("Could not load text_style_class for widget '%s': %s"), *Widget->GetName(), *StyleClassPath);
		return false;
	}

	CommonTextBlock->SetStyle(StyleClass);
	return true;
}

static EHorizontalAlignment ReadHAlign(const TSharedPtr<FJsonObject>& Obj, EHorizontalAlignment Default)
{
	FString S;
	if (Obj.IsValid() && Obj->TryGetStringField(TEXT("h_align"), S))
	{
		if (S.Equals(TEXT("left"), ESearchCase::IgnoreCase))   return HAlign_Left;
		if (S.Equals(TEXT("center"), ESearchCase::IgnoreCase)) return HAlign_Center;
		if (S.Equals(TEXT("right"), ESearchCase::IgnoreCase))  return HAlign_Right;
		if (S.Equals(TEXT("fill"), ESearchCase::IgnoreCase))   return HAlign_Fill;
	}
	return Default;
}

static EVerticalAlignment ReadVAlign(const TSharedPtr<FJsonObject>& Obj, EVerticalAlignment Default)
{
	FString S;
	if (Obj.IsValid() && Obj->TryGetStringField(TEXT("v_align"), S))
	{
		if (S.Equals(TEXT("top"), ESearchCase::IgnoreCase))    return VAlign_Top;
		if (S.Equals(TEXT("center"), ESearchCase::IgnoreCase)) return VAlign_Center;
		if (S.Equals(TEXT("bottom"), ESearchCase::IgnoreCase)) return VAlign_Bottom;
		if (S.Equals(TEXT("fill"), ESearchCase::IgnoreCase))   return VAlign_Fill;
	}
	return Default;
}

static FSlateChildSize ReadChildSize(const TSharedPtr<FJsonObject>& SlotObject, const FSlateChildSize& Default)
{
	const TSharedPtr<FJsonObject>* SizeObj = nullptr;
	if (!SlotObject.IsValid() || !SlotObject->TryGetObjectField(TEXT("size"), SizeObj) || SizeObj == nullptr)
	{
		return Default;
	}
	double FillRatio = 0.0;
	if ((*SizeObj)->TryGetNumberField(TEXT("fill"), FillRatio))
	{
		FSlateChildSize Size(ESlateSizeRule::Fill);
		Size.Value = static_cast<float>(FillRatio);
		return Size;
	}
	bool bAuto = false;
	if ((*SizeObj)->TryGetBoolField(TEXT("auto"), bAuto) && bAuto)
	{
		return FSlateChildSize(ESlateSizeRule::Automatic);
	}
	return Default;
}

static bool SetEnumPropertyByName(UObject* Object, const FName PropertyName, const TArray<FString>& CandidateNames)
{
	if (!Object)
	{
		return false;
	}

	if (FEnumProperty* EnumProperty = FindFProperty<FEnumProperty>(Object->GetClass(), PropertyName))
	{
		UEnum* Enum = EnumProperty->GetEnum();
		for (const FString& CandidateName : CandidateNames)
		{
			const int64 Value = Enum ? Enum->GetValueByNameString(CandidateName) : INDEX_NONE;
			if (Value != INDEX_NONE)
			{
				EnumProperty->GetUnderlyingProperty()->SetIntPropertyValue(
					EnumProperty->ContainerPtrToValuePtr<void>(Object),
					Value
				);
				return true;
			}
		}
	}

	if (FByteProperty* ByteProperty = FindFProperty<FByteProperty>(Object->GetClass(), PropertyName))
	{
		UEnum* Enum = ByteProperty->Enum;
		for (const FString& CandidateName : CandidateNames)
		{
			const int64 Value = Enum ? Enum->GetValueByNameString(CandidateName) : INDEX_NONE;
			if (Value != INDEX_NONE)
			{
				ByteProperty->SetPropertyValue_InContainer(Object, static_cast<uint8>(Value));
				return true;
			}
		}
	}

	return false;
}

static void ApplyBoxSlotProps(UPanelSlot* Slot, const TSharedPtr<FJsonObject>& SlotObject)
{
	if (!Slot || !SlotObject.IsValid()) return;

	if (UHorizontalBoxSlot* H = Cast<UHorizontalBoxSlot>(Slot))
	{
		H->SetPadding(ReadMargin(SlotObject, TEXT("padding"), H->GetPadding()));
		H->SetSize(ReadChildSize(SlotObject, H->GetSize()));
		H->SetHorizontalAlignment(ReadHAlign(SlotObject, H->GetHorizontalAlignment()));
		H->SetVerticalAlignment(ReadVAlign(SlotObject, H->GetVerticalAlignment()));
		return;
	}
	if (UVerticalBoxSlot* V = Cast<UVerticalBoxSlot>(Slot))
	{
		V->SetPadding(ReadMargin(SlotObject, TEXT("padding"), V->GetPadding()));
		V->SetSize(ReadChildSize(SlotObject, V->GetSize()));
		V->SetHorizontalAlignment(ReadHAlign(SlotObject, V->GetHorizontalAlignment()));
		V->SetVerticalAlignment(ReadVAlign(SlotObject, V->GetVerticalAlignment()));
		return;
	}
	if (UOverlaySlot* O = Cast<UOverlaySlot>(Slot))
	{
		O->SetPadding(ReadMargin(SlotObject, TEXT("padding"), O->GetPadding()));
		O->SetHorizontalAlignment(ReadHAlign(SlotObject, O->GetHorizontalAlignment()));
		O->SetVerticalAlignment(ReadVAlign(SlotObject, O->GetVerticalAlignment()));
		return;
	}
	if (UScrollBoxSlot* S = Cast<UScrollBoxSlot>(Slot))
	{
		S->SetPadding(ReadMargin(SlotObject, TEXT("padding"), S->GetPadding()));
		S->SetHorizontalAlignment(ReadHAlign(SlotObject, S->GetHorizontalAlignment()));
		return;
	}
	if (UWrapBoxSlot* W = Cast<UWrapBoxSlot>(Slot))
	{
		W->SetPadding(ReadMargin(SlotObject, TEXT("padding"), W->GetPadding()));
		W->SetHorizontalAlignment(ReadHAlign(SlotObject, W->GetHorizontalAlignment()));
		W->SetVerticalAlignment(ReadVAlign(SlotObject, W->GetVerticalAlignment()));
		return;
	}
	if (UBorderSlot* B = Cast<UBorderSlot>(Slot))
	{
		B->SetPadding(ReadMargin(SlotObject, TEXT("padding"), B->GetPadding()));
		B->SetHorizontalAlignment(ReadHAlign(SlotObject, B->GetHorizontalAlignment()));
		B->SetVerticalAlignment(ReadVAlign(SlotObject, B->GetVerticalAlignment()));
		return;
	}
	if (UWidgetSwitcherSlot* WS = Cast<UWidgetSwitcherSlot>(Slot))
	{
		WS->SetPadding(ReadMargin(SlotObject, TEXT("padding"), WS->GetPadding()));
		WS->SetHorizontalAlignment(ReadHAlign(SlotObject, WS->GetHorizontalAlignment()));
		WS->SetVerticalAlignment(ReadVAlign(SlotObject, WS->GetVerticalAlignment()));
		return;
	}
}

bool ApplyWidgetProperties(UWidget* Widget, const TSharedPtr<FJsonObject>& Node, FString& OutError)
{
	if (!Widget || !Node.IsValid())
	{
		OutError = TEXT("Cannot apply properties to a null widget or JSON node.");
		return false;
	}

	FString Text;
	if (Node->TryGetStringField(TEXT("text"), Text))
	{
		if (UTextBlock* TextBlock = Cast<UTextBlock>(Widget))
		{
			TextBlock->SetText(FText::FromString(Text));
		}
		else if (UEditableTextBox* EditableTextBox = Cast<UEditableTextBox>(Widget))
		{
			EditableTextBox->SetText(FText::FromString(Text));
		}
		else if (UAGSButtonBase* AGSBtn = Cast<UAGSButtonBase>(Widget))
		{
			AGSBtn->DefaultLabel = FText::FromString(Text);
		}

		if (FTextProperty* TextProperty = FindFProperty<FTextProperty>(Widget->GetClass(), TEXT("ButtonText")))
		{
			TextProperty->SetPropertyValue_InContainer(Widget, FText::FromString(Text));
		}
	}

	bool bAutoWrap = false;
	if (Node->TryGetBoolField(TEXT("auto_wrap"), bAutoWrap))
	{
		if (UTextBlock* TextBlock = Cast<UTextBlock>(Widget))
		{
			TextBlock->SetAutoWrapText(bAutoWrap);
		}
	}

	FString HintText;
	if (Node->TryGetStringField(TEXT("hint_text"), HintText))
	{
		if (UEditableTextBox* EditableTextBox = Cast<UEditableTextBox>(Widget))
		{
			EditableTextBox->SetHintText(FText::FromString(HintText));
		}
		else if (UAGSTextInputBase* AGSInput = Cast<UAGSTextInputBase>(Widget))
		{
			AGSInput->DefaultHintText = FText::FromString(HintText);
		}
	}

	bool bIsPassword = false;
	if (Node->TryGetBoolField(TEXT("is_password"), bIsPassword))
	{
		if (UEditableTextBox* EditableTextBox = Cast<UEditableTextBox>(Widget))
		{
			EditableTextBox->SetIsPassword(bIsPassword);
		}
	}

	const TSharedPtr<FJsonObject>* StyleObjectPtr = nullptr;
	TSharedPtr<FJsonObject> StyleObject;
	if (Node->TryGetObjectField(TEXT("style"), StyleObjectPtr) && StyleObjectPtr)
	{
		StyleObject = *StyleObjectPtr;
	}

	if (!ApplyCommonButtonStyle(Widget, Node, OutError) || !ApplyCommonTextStyle(Widget, Node, OutError))
	{
		return false;
	}

	if (StyleObject.IsValid() && StyleObject->HasTypedField<EJson::Array>(TEXT("color")))
	{
		const TArray<TSharedPtr<FJsonValue>> ColorValues = StyleObject->GetArrayField(TEXT("color"));
		if (ColorValues.Num() >= 4)
		{
			const FLinearColor Color(
				static_cast<float>(ColorValues[0]->AsNumber()),
				static_cast<float>(ColorValues[1]->AsNumber()),
				static_cast<float>(ColorValues[2]->AsNumber()),
				static_cast<float>(ColorValues[3]->AsNumber())
			);
			const FSlateColor SlateColor(Color);

			if (UTextBlock* TextBlock = Cast<UTextBlock>(Widget))
			{
				TextBlock->SetColorAndOpacity(SlateColor);
			}
			else if (UButton* Button = Cast<UButton>(Widget))
			{
				Button->SetBackgroundColor(Color);
			}
			else if (UEditableTextBox* EditableTextBox = Cast<UEditableTextBox>(Widget))
			{
				EditableTextBox->WidgetStyle.SetForegroundColor(SlateColor);
				EditableTextBox->WidgetStyle.SetFocusedForegroundColor(SlateColor);
				EditableTextBox->WidgetStyle.SetReadOnlyForegroundColor(SlateColor);
				EditableTextBox->WidgetStyle.TextStyle.SetColorAndOpacity(SlateColor);
			}
		}
	}

	if (StyleObject.IsValid() && StyleObject->HasTypedField<EJson::Array>(TEXT("hint_color")))
	{
		const TArray<TSharedPtr<FJsonValue>> HintColorValues = StyleObject->GetArrayField(TEXT("hint_color"));
		if (HintColorValues.Num() >= 4)
		{
			const FLinearColor HintColor(
				static_cast<float>(HintColorValues[0]->AsNumber()),
				static_cast<float>(HintColorValues[1]->AsNumber()),
				static_cast<float>(HintColorValues[2]->AsNumber()),
				static_cast<float>(HintColorValues[3]->AsNumber())
			);

			if (UEditableTextBox* EditableTextBox = Cast<UEditableTextBox>(Widget);
				EditableTextBox && !StyleObject->HasTypedField<EJson::Array>(TEXT("color")))
			{
				EditableTextBox->WidgetStyle.TextStyle.SetColorAndOpacity(FSlateColor(HintColor));
			}
		}
	}

	FString BrushPath;
	if (Node->TryGetStringField(TEXT("brush"), BrushPath))
	{
		if (UImage* Image = Cast<UImage>(Widget))
		{
			if (UTexture2D* Texture = LoadObject<UTexture2D>(nullptr, *BrushPath))
			{
				Image->SetBrushFromTexture(Texture, /*bMatchSize=*/false);
				Image->Modify();
			}
			else
			{
				UE_LOG(LogAccelByteUITools, Warning, TEXT("ApplyWidgetProperties: could not load brush texture '%s' for widget '%s'"),
					*BrushPath, *Widget->GetName());
			}
		}
	}

	if (StyleObject.IsValid() && StyleObject->HasTypedField<EJson::Array>(TEXT("background_color")))
	{
		const TArray<TSharedPtr<FJsonValue>> Bg = StyleObject->GetArrayField(TEXT("background_color"));
		if (Bg.Num() >= 4)
		{
			const FLinearColor BgColor(
				static_cast<float>(Bg[0]->AsNumber()),
				static_cast<float>(Bg[1]->AsNumber()),
				static_cast<float>(Bg[2]->AsNumber()),
				static_cast<float>(Bg[3]->AsNumber())
			);
			if (UBorder* Border = Cast<UBorder>(Widget))
			{
				Border->SetBrushColor(BgColor);
			}
			else if (UImage* Image = Cast<UImage>(Widget))
			{
				Image->SetColorAndOpacity(BgColor);
			}
			else if (UEditableTextBox* EditableTextBox = Cast<UEditableTextBox>(Widget))
			{
				EditableTextBox->WidgetStyle.SetBackgroundColor(FSlateColor(BgColor));
				EditableTextBox->WidgetStyle.BackgroundImageNormal.TintColor = FSlateColor(BgColor);
				EditableTextBox->WidgetStyle.BackgroundImageHovered.TintColor = FSlateColor(BgColor);
				EditableTextBox->WidgetStyle.BackgroundImageFocused.TintColor = FSlateColor(BgColor);
				EditableTextBox->WidgetStyle.BackgroundImageReadOnly.TintColor = FSlateColor(BgColor);
			}
		}
	}

	if (UBorder* Border = Cast<UBorder>(Widget))
	{
		if (Node->HasTypedField<EJson::Array>(TEXT("padding")))
		{
			Border->SetPadding(ReadMargin(Node, TEXT("padding"), Border->GetPadding()));
		}
		ApplyRoundedBoxStyleToBorder(Border, StyleObject);
	}
	if (UButton* Button = Cast<UButton>(Widget))
	{
		ApplyRoundedBoxStyleToButton(Button, StyleObject);
		if (Node->HasTypedField<EJson::Array>(TEXT("padding")))
		{
			FButtonStyle ButtonStyle = Button->GetStyle();
			const FMargin ButtonPadding = ReadMargin(Node, TEXT("padding"), ButtonStyle.NormalPadding);
			ButtonStyle.SetNormalPadding(ButtonPadding);
			ButtonStyle.SetPressedPadding(ButtonPadding);
			Button->SetStyle(ButtonStyle);
		}
	}
	if (UEditableTextBox* EditableTextBox = Cast<UEditableTextBox>(Widget))
	{
		ApplyRoundedBoxStyleToEditableTextBox(EditableTextBox, StyleObject);
		if (Node->HasTypedField<EJson::Array>(TEXT("padding")))
		{
			EditableTextBox->WidgetStyle.SetPadding(ReadMargin(Node, TEXT("padding"), EditableTextBox->WidgetStyle.Padding));
		}
	}

	if (USizeBox* SizeBox = Cast<USizeBox>(Widget))
	{
		double Width = 0.0;
		if (Node->TryGetNumberField(TEXT("width"), Width))
		{
			SizeBox->SetWidthOverride(static_cast<float>(Width));
		}
		double Height = 0.0;
		if (Node->TryGetNumberField(TEXT("height"), Height))
		{
			SizeBox->SetHeightOverride(static_cast<float>(Height));
		}
	}

	FString EntryWidgetClassPath;
	if (Node->TryGetStringField(TEXT("entry_widget_class"), EntryWidgetClassPath))
	{
		UListViewBase* CollectionWidget = Cast<UListViewBase>(Widget);
		if (!CollectionWidget)
		{
			OutError = FString::Printf(
				TEXT("Widget '%s' declares entry_widget_class but is not a ListView, TileView, or TreeView."),
				*Widget->GetName());
			return false;
		}

		UClass* EntryWidgetClass = LoadClass<UUserWidget>(nullptr, *EntryWidgetClassPath);
		if (!EntryWidgetClass)
		{
			OutError = FString::Printf(
				TEXT("Entry widget class could not be loaded for widget '%s': %s"),
				*Widget->GetName(),
				*EntryWidgetClassPath);
			return false;
		}

		if (!EntryWidgetClass->ImplementsInterface(UUserObjectListEntry::StaticClass()))
		{
			OutError = FString::Printf(
				TEXT("Entry widget class for widget '%s' must implement UserObjectListEntry: %s"),
				*Widget->GetName(),
				*EntryWidgetClassPath);
			return false;
		}

		CollectionWidget->Modify();
		if (FClassProperty* EntryWidgetClassProperty = FindFProperty<FClassProperty>(CollectionWidget->GetClass(), TEXT("EntryWidgetClass")))
		{
			EntryWidgetClassProperty->SetObjectPropertyValue_InContainer(CollectionWidget, EntryWidgetClass);
		}
		else
		{
			OutError = FString::Printf(
				TEXT("Widget '%s' does not expose an EntryWidgetClass property."),
				*Widget->GetName());
			return false;
		}
	}

	FString SelectionMode;
	if (Node->TryGetStringField(TEXT("selection_mode"), SelectionMode))
	{
		Widget->Modify();
		if (SelectionMode.Equals(TEXT("none"), ESearchCase::IgnoreCase))
		{
			SetEnumPropertyByName(Widget, TEXT("SelectionMode"), { TEXT("None"), TEXT("ESelectionMode::None") });
		}
		else if (SelectionMode.Equals(TEXT("single"), ESearchCase::IgnoreCase))
		{
			SetEnumPropertyByName(Widget, TEXT("SelectionMode"), { TEXT("Single"), TEXT("ESelectionMode::Single") });
		}
		else if (SelectionMode.Equals(TEXT("multi"), ESearchCase::IgnoreCase))
		{
			SetEnumPropertyByName(Widget, TEXT("SelectionMode"), { TEXT("Multi"), TEXT("ESelectionMode::Multi") });
		}
	}

	FString Orientation;
	if (Node->TryGetStringField(TEXT("orientation"), Orientation))
	{
		Widget->Modify();
		if (Orientation.Equals(TEXT("horizontal"), ESearchCase::IgnoreCase))
		{
			SetEnumPropertyByName(Widget, TEXT("Orientation"), { TEXT("Orient_Horizontal"), TEXT("EOrientation::Orient_Horizontal") });
		}
		else if (Orientation.Equals(TEXT("vertical"), ESearchCase::IgnoreCase))
		{
			SetEnumPropertyByName(Widget, TEXT("Orientation"), { TEXT("Orient_Vertical"), TEXT("EOrientation::Orient_Vertical") });
		}
	}

	if (UTileView* TileView = Cast<UTileView>(Widget))
	{
		double EntryWidth = 0.0;
		if (Node->TryGetNumberField(TEXT("entry_width"), EntryWidth))
		{
			TileView->Modify();
			TileView->SetEntryWidth(static_cast<float>(EntryWidth));
		}

		double EntryHeight = 0.0;
		if (Node->TryGetNumberField(TEXT("entry_height"), EntryHeight))
		{
			TileView->Modify();
			TileView->SetEntryHeight(static_cast<float>(EntryHeight));
		}
	}

	if (UListView* ListView = Cast<UListView>(Widget))
	{
		ListView->Modify();
		ListView->SetClipping(EWidgetClipping::ClipToBounds);

		double HorizontalEntrySpacing = 0.0;
		if (Node->TryGetNumberField(TEXT("horizontal_entry_spacing"), HorizontalEntrySpacing))
		{
			ListView->Modify();
			ListView->SetHorizontalEntrySpacing(static_cast<float>(FMath::Max(0.0, HorizontalEntrySpacing)));
		}

		double VerticalEntrySpacing = 0.0;
		if (Node->TryGetNumberField(TEXT("vertical_entry_spacing"), VerticalEntrySpacing))
		{
			ListView->Modify();
			ListView->SetVerticalEntrySpacing(static_cast<float>(FMath::Max(0.0, VerticalEntrySpacing)));
		}
	}

	return true;
}

bool AttachWidget(UWidget* Parent, UWidget* Child, const TSharedPtr<FJsonObject>& ChildNode, FString& OutError)
{
	if (!Parent || !Child)
	{
		OutError = TEXT("Cannot attach a null widget.");
		return false;
	}

	if (UCanvasPanel* CanvasPanel = Cast<UCanvasPanel>(Parent))
	{
		UCanvasPanelSlot* CanvasSlot = CanvasPanel->AddChildToCanvas(Child);
		if (!CanvasSlot)
		{
			OutError = FString::Printf(TEXT("Failed to attach '%s' to CanvasPanel '%s'."), *Child->GetName(), *Parent->GetName());
			return false;
		}

		const TSharedPtr<FJsonObject>* SlotObject = nullptr;
		if (ChildNode.IsValid() && ChildNode->TryGetObjectField(TEXT("slot"), SlotObject))
		{
			CanvasSlot->SetAnchors(ReadAnchors(*SlotObject, TEXT("anchors"), CanvasSlot->GetAnchors()));
			CanvasSlot->SetAlignment(ReadVector2D(*SlotObject, TEXT("alignment"), CanvasSlot->GetAlignment()));

			if ((*SlotObject)->HasTypedField<EJson::Array>(TEXT("offsets")))
			{
				CanvasSlot->SetOffsets(ReadMargin(*SlotObject, TEXT("offsets"), FMargin(0.0f)));
			}
			else
			{
				CanvasSlot->SetPosition(ReadVector2D(*SlotObject, TEXT("position"), FVector2D::ZeroVector));
				CanvasSlot->SetSize(ReadVector2D(*SlotObject, TEXT("size"), FVector2D(100.0f, 40.0f)));
			}

			bool bAutoSize = false;
			(*SlotObject)->TryGetBoolField(TEXT("auto_size"), bAutoSize);
			if (bAutoSize)
			{
				CanvasSlot->SetAutoSize(true);
			}
		}
		return true;
	}

	if (UUniformGridPanel* GridPanel = Cast<UUniformGridPanel>(Parent))
	{
		UUniformGridSlot* GridSlot = Cast<UUniformGridSlot>(GridPanel->AddChild(Child));
		if (!GridSlot)
		{
			OutError = FString::Printf(TEXT("Failed to attach '%s' to UniformGridPanel '%s'."), *Child->GetName(), *Parent->GetName());
			return false;
		}

		const TSharedPtr<FJsonObject>* SlotObject = nullptr;
		if (ChildNode.IsValid() && ChildNode->TryGetObjectField(TEXT("slot"), SlotObject))
		{
			int32 Row = 0;
			int32 Column = 0;
			(*SlotObject)->TryGetNumberField(TEXT("row"), Row);
			(*SlotObject)->TryGetNumberField(TEXT("column"), Column);
			GridSlot->SetRow(Row);
			GridSlot->SetColumn(Column);
		}
		return true;
	}

	if (UPanelWidget* PanelWidget = Cast<UPanelWidget>(Parent))
	{
		UPanelSlot* NewSlot = PanelWidget->AddChild(Child);
		if (NewSlot)
		{
			const TSharedPtr<FJsonObject>* SlotObject = nullptr;
			if (ChildNode.IsValid() && ChildNode->TryGetObjectField(TEXT("slot"), SlotObject))
			{
				ApplyBoxSlotProps(NewSlot, *SlotObject);
			}
			return true;
		}

		OutError = FString::Printf(TEXT("Failed to attach '%s' to panel '%s'."), *Child->GetName(), *Parent->GetName());
		return false;
	}

	if (UContentWidget* ContentWidget = Cast<UContentWidget>(Parent))
	{
		ContentWidget->SetContent(Child);
		return true;
	}

	OutError = FString::Printf(TEXT("Widget '%s' cannot contain child '%s'."), *Parent->GetName(), *Child->GetName());
	return false;
}

UWidget* BuildWidgetNode(UWidgetTree* WidgetTree, const TSharedPtr<FJsonObject>& Node, FString& OutError)
{
	if (!WidgetTree || !Node.IsValid())
	{
		OutError = TEXT("Invalid widget tree or JSON node.");
		return nullptr;
	}

	FString WidgetType;
	FString WidgetName;
	if (!Node->TryGetStringField(TEXT("type"), WidgetType) || !Node->TryGetStringField(TEXT("name"), WidgetName))
	{
		OutError = TEXT("Widget node requires string fields 'type' and 'name'.");
		return nullptr;
	}

	UClass* WidgetClass = ResolveWidgetClass(Node);
	if (!WidgetClass)
	{
		OutError = FString::Printf(TEXT("Unsupported widget type: %s"), *WidgetType);
		return nullptr;
	}

	UWidget* Widget = WidgetTree->ConstructWidget<UWidget>(WidgetClass, FName(*WidgetName));
	if (!Widget)
	{
		OutError = FString::Printf(TEXT("Failed to construct widget: %s"), *WidgetName);
		return nullptr;
	}

	bool bIsVariable = false;
	Node->TryGetBoolField(TEXT("is_variable"), bIsVariable);
	Widget->bIsVariable = bIsVariable;
	if (!ApplyWidgetProperties(Widget, Node, OutError))
	{
		return nullptr;
	}

	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (Node->TryGetArrayField(TEXT("children"), Children))
	{
		for (const TSharedPtr<FJsonValue>& ChildValue : *Children)
		{
			UWidget* ChildWidget = BuildWidgetNode(WidgetTree, ChildValue->AsObject(), OutError);
			if (!ChildWidget || !AttachWidget(Widget, ChildWidget, ChildValue->AsObject(), OutError))
			{
				return nullptr;
			}
		}
	}

	return Widget;
}

UPanelWidget* FindPanelWidgetByName(UWidgetTree* WidgetTree, const FString& WidgetName)
{
	if (!WidgetTree)
	{
		return nullptr;
	}

	return Cast<UPanelWidget>(WidgetTree->FindWidget(FName(*WidgetName)));
}

void CollectWidgetNames(UWidget* Widget, TArray<FString>& OutWidgetNames)
{
	if (!Widget)
	{
		return;
	}

	OutWidgetNames.Add(Widget->GetName());

	if (const UPanelWidget* PanelWidget = Cast<UPanelWidget>(Widget))
	{
		for (int32 ChildIndex = 0; ChildIndex < PanelWidget->GetChildrenCount(); ++ChildIndex)
		{
			CollectWidgetNames(PanelWidget->GetChildAt(ChildIndex), OutWidgetNames);
		}
	}
	else if (const UContentWidget* ContentWidget = Cast<UContentWidget>(Widget))
	{
		CollectWidgetNames(ContentWidget->GetContent(), OutWidgetNames);
	}
}

void MoveWidgetToTransientPackage(UWidget* Widget)
{
	if (!Widget)
	{
		return;
	}

	Widget->Modify();
	Widget->Rename(nullptr, GetTransientPackage(), REN_DontCreateRedirectors | REN_NonTransactional);
}

void RemoveWidgetTreeSourceWidgets(UWidgetBlueprint* WidgetBlueprint)
{
	if (!WidgetBlueprint || !WidgetBlueprint->WidgetTree)
	{
		return;
	}

	UWidgetTree* WidgetTree = WidgetBlueprint->WidgetTree;
	TArray<UWidget*> SourceWidgets;
	WidgetBlueprint->ForEachSourceWidget([&SourceWidgets](UWidget* Widget)
	{
		if (Widget)
		{
			SourceWidgets.Add(Widget);
		}
	});

	WidgetTree->RootWidget = nullptr;
	for (UWidget* SourceWidget : SourceWidgets)
	{
		if (SourceWidget)
		{
			WidgetTree->RemoveWidget(SourceWidget);
		}
	}

	for (UWidget* SourceWidget : SourceWidgets)
	{
		MoveWidgetToTransientPackage(SourceWidget);
	}
}

void RemoveGeneratedWidget(UWidgetBlueprint* WidgetBlueprint, UWidget* Widget)
{
	if (!WidgetBlueprint || !WidgetBlueprint->WidgetTree || !Widget)
	{
		return;
	}

	TArray<UWidget*> WidgetsToMove;
	WidgetsToMove.Add(Widget);
	UWidgetTree::GetChildWidgets(Widget, WidgetsToMove);

	WidgetBlueprint->WidgetTree->RemoveWidget(Widget);
	for (UWidget* WidgetToMove : WidgetsToMove)
	{
		MoveWidgetToTransientPackage(WidgetToMove);
	}
}

bool HasParentClassProperty(const UWidgetBlueprint* WidgetBlueprint, const FName PropertyName)
{
	if (!WidgetBlueprint || PropertyName.IsNone())
	{
		return false;
	}

	for (const UClass* ParentClass = WidgetBlueprint->ParentClass; ParentClass; ParentClass = ParentClass->GetSuperClass())
	{
		if (ParentClass->FindPropertyByName(PropertyName))
		{
			return true;
		}
	}

	return false;
}

void ReconcileWidgetVariables(UWidgetBlueprint* WidgetBlueprint)
{
	if (!WidgetBlueprint)
	{
		return;
	}

	TSet<FName> SourceWidgetNames;
	WidgetBlueprint->ForEachSourceWidget([WidgetBlueprint, &SourceWidgetNames](UWidget* Widget)
	{
		if (!Widget)
		{
			return;
		}

		const FName WidgetName = Widget->GetFName();
		if (Widget->bIsVariable && HasParentClassProperty(WidgetBlueprint, WidgetName))
		{
			Widget->Modify();
			Widget->bIsVariable = false;
		}

		SourceWidgetNames.Add(WidgetName);
	});

	for (UWidgetAnimation* Animation : WidgetBlueprint->Animations)
	{
		if (Animation)
		{
			SourceWidgetNames.Add(Animation->GetFName());
		}
	}

	TArray<FName> RemovedVariableNames;
	for (const TPair<FName, FGuid>& ExistingVariable : WidgetBlueprint->WidgetVariableNameToGuidMap)
	{
		if (!SourceWidgetNames.Contains(ExistingVariable.Key))
		{
			RemovedVariableNames.Add(ExistingVariable.Key);
		}
	}

	for (const FName& RemovedVariableName : RemovedVariableNames)
	{
		WidgetBlueprint->OnVariableRemoved(RemovedVariableName);
	}

	for (const FName& SourceWidgetName : SourceWidgetNames)
	{
		if (!WidgetBlueprint->WidgetVariableNameToGuidMap.Contains(SourceWidgetName))
		{
			WidgetBlueprint->OnVariableAdded(SourceWidgetName);
		}
	}
}

struct FCollectionEntryExpectation
{
	FString WidgetName;
	FString EntryWidgetClassPath;
};

struct FWidgetClassExpectation
{
	FString WidgetName;
	FString ExpectedClassPath;
};

bool ContainsStaleLiveCodingClassMarker(const FString& Value)
{
	const FString UpperValue = Value.ToUpper();
	return UpperValue.Contains(TEXT("LIVE CODING"))
		|| UpperValue.Contains(TEXT("LIVECODING"))
		|| UpperValue.Contains(TEXT("HOTRELOAD"))
		|| UpperValue.Contains(TEXT("HOTRELOADED"))
		|| UpperValue.Contains(TEXT("REINST_"))
		|| UpperValue.Contains(TEXT("SKEL_"))
		|| UpperValue.Contains(TEXT("TRASHCLASS"))
		|| UpperValue.Contains(TEXT("/ENGINE/TRANSIENT"))
		|| UpperValue.Contains(TEXT("TRANSIENT."));
}

bool FindStaleLiveCodingClassInChain(const UClass* Class, FString& OutStaleClassPath)
{
	for (const UClass* CurrentClass = Class; CurrentClass; CurrentClass = CurrentClass->GetSuperClass())
	{
		const FString ClassIdentity = FString::Printf(
			TEXT("%s %s %s"),
			*CurrentClass->GetName(),
			*CurrentClass->GetPathName(),
			*CurrentClass->GetFullName());
		if (ContainsStaleLiveCodingClassMarker(ClassIdentity))
		{
			OutStaleClassPath = CurrentClass->GetPathName();
			return true;
		}
	}

	OutStaleClassPath.Reset();
	return false;
}

FString StaleLiveCodingClassMessage(
	const FString& WidgetName,
	const FString& ExpectedClassPath,
	const FString& ActualClassPath,
	const FString& StaleClassPath)
{
	const FString DisplayName = StaleClassPath.IsEmpty() ? ActualClassPath : StaleClassPath;
	return FString::Printf(
		TEXT("The editor has stale Live Coding class state for '%s'. Restart the editor or run a full rebuild, then regenerate. Widget '%s' expected '%s', actual '%s'."),
		DisplayName.IsEmpty() ? TEXT("<unknown>") : *DisplayName,
		*WidgetName,
		*ExpectedClassPath,
		ActualClassPath.IsEmpty() ? TEXT("<none>") : *ActualClassPath);
}

UClass* ExpectedNativeWidgetClass(const FString& WidgetType)
{
	if (WidgetType == TEXT("CanvasPanel"))
	{
		return UCanvasPanel::StaticClass();
	}
	if (WidgetType == TEXT("Overlay"))
	{
		return UOverlay::StaticClass();
	}
	if (WidgetType == TEXT("VerticalBox"))
	{
		return UVerticalBox::StaticClass();
	}
	if (WidgetType == TEXT("HorizontalBox"))
	{
		return UHorizontalBox::StaticClass();
	}
	if (WidgetType == TEXT("SizeBox"))
	{
		return USizeBox::StaticClass();
	}
	if (WidgetType == TEXT("Border"))
	{
		return UBorder::StaticClass();
	}
	if (WidgetType == TEXT("SafeZone"))
	{
		return USafeZone::StaticClass();
	}
	if (WidgetType == TEXT("ScaleBox"))
	{
		return UScaleBox::StaticClass();
	}
	if (WidgetType == TEXT("TextBlock"))
	{
		return UTextBlock::StaticClass();
	}
	if (WidgetType == TEXT("Button"))
	{
		return UButton::StaticClass();
	}
	if (WidgetType == TEXT("EditableTextBox"))
	{
		return UEditableTextBox::StaticClass();
	}
	if (WidgetType == TEXT("Image"))
	{
		return UImage::StaticClass();
	}
	if (WidgetType == TEXT("Spacer"))
	{
		return USpacer::StaticClass();
	}
	if (WidgetType == TEXT("ScrollBox"))
	{
		return UScrollBox::StaticClass();
	}
	if (WidgetType == TEXT("ListView"))
	{
		return UListView::StaticClass();
	}
	if (WidgetType == TEXT("TileView"))
	{
		return UTileView::StaticClass();
	}
	if (WidgetType == TEXT("TreeView"))
	{
		return UTreeView::StaticClass();
	}
	if (WidgetType == TEXT("WidgetSwitcher"))
	{
		return UWidgetSwitcher::StaticClass();
	}
	if (WidgetType == TEXT("UniformGridPanel"))
	{
		return UUniformGridPanel::StaticClass();
	}
	if (WidgetType == TEXT("WrapBox"))
	{
		return UWrapBox::StaticClass();
	}
	return nullptr;
}

UClass* ExpectedAgsCoreWidgetClass(const FString& WidgetType, const FString& ClassPath)
{
	// When class_path points to a project-specific Blueprint (/Game/...), resolve the
	// expected C++ class by walking up the Blueprint's native parent chain. This lets
	// project button classes (e.g. UAccelByteWarsButtonBase) pass binding verification
	// without requiring them to extend UAGSButtonBase.
	if (ClassPath.StartsWith(TEXT("/Game/")))
	{
		if (UClass* BlueprintClass = LoadClass<UUserWidget>(nullptr, *ClassPath))
		{
			UClass* NativeParent = BlueprintClass;
			while (NativeParent && NativeParent->HasAnyClassFlags(CLASS_CompiledFromBlueprint))
			{
				NativeParent = NativeParent->GetSuperClass();
			}
			if (NativeParent && NativeParent != UObject::StaticClass() && NativeParent != UUserWidget::StaticClass())
			{
				return NativeParent;
			}
		}
		// Blueprint not yet loaded in editor — fall through to AGS contract as best-effort.
	}

	const bool bIsButton =
		WidgetType == TEXT("AGSBaseButton")
		|| WidgetType == TEXT("AGSButton")
		|| WidgetType == TEXT("AGSSecondaryButton")
		|| WidgetType == TEXT("AGSDangerButton")
		|| ClassPath.EndsWith(TEXT("/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C"))
		|| ClassPath.EndsWith(TEXT("/WBP_AGS_SecondaryButton.WBP_AGS_SecondaryButton_C"))
		|| ClassPath.EndsWith(TEXT("/WBP_AGS_DangerButton.WBP_AGS_DangerButton_C"));
	if (bIsButton)
	{
		return UAGSButtonBase::StaticClass();
	}
	if (WidgetType == TEXT("AGSIconButton") || ClassPath.EndsWith(TEXT("/WBP_AGS_IconButton.WBP_AGS_IconButton_C")))
	{
		return UAGSIconButtonBase::StaticClass();
	}
	if (WidgetType == TEXT("AGSTextInput")
		|| WidgetType == TEXT("AGSPasswordInput")
		|| WidgetType == TEXT("AGSSearchInput")
		|| ClassPath.EndsWith(TEXT("/WBP_AGS_TextInput.WBP_AGS_TextInput_C"))
		|| ClassPath.EndsWith(TEXT("/WBP_AGS_PasswordInput.WBP_AGS_PasswordInput_C"))
		|| ClassPath.EndsWith(TEXT("/WBP_AGS_SearchInput.WBP_AGS_SearchInput_C")))
	{
		return UAGSTextInputBase::StaticClass();
	}
	if (WidgetType == TEXT("AGSStatusMessage") || ClassPath.EndsWith(TEXT("/WBP_AGS_StatusMessage.WBP_AGS_StatusMessage_C")))
	{
		return UAGSStatusMessageBase::StaticClass();
	}
	if (WidgetType == TEXT("AGSLoadingIndicator") || ClassPath.EndsWith(TEXT("/WBP_AGS_LoadingIndicator.WBP_AGS_LoadingIndicator_C")))
	{
		return UAGSLoadingIndicatorBase::StaticClass();
	}
	if (WidgetType == TEXT("AGSEmptyState") || ClassPath.EndsWith(TEXT("/WBP_AGS_EmptyState.WBP_AGS_EmptyState_C")))
	{
		return UAGSEmptyStateBase::StaticClass();
	}
	if (WidgetType == TEXT("AGSErrorState") || ClassPath.EndsWith(TEXT("/WBP_AGS_ErrorState.WBP_AGS_ErrorState_C")))
	{
		return UAGSErrorStateBase::StaticClass();
	}
	if (WidgetType == TEXT("AGSModalPanel") || ClassPath.EndsWith(TEXT("/WBP_AGS_ModalPanel.WBP_AGS_ModalPanel_C")))
	{
		return UAGSActionPanelBase::StaticClass();
	}
	if (WidgetType == TEXT("AGSBasePanel") || ClassPath.EndsWith(TEXT("/WBP_AGS_BasePanel.WBP_AGS_BasePanel_C")))
	{
		return UAGSBasePanelBase::StaticClass();
	}
	if (WidgetType == TEXT("AGSAvatar") || ClassPath.EndsWith(TEXT("/WBP_AGS_Avatar.WBP_AGS_Avatar_C")))
	{
		return UAGSAvatarBase::StaticClass();
	}
	// Common UI-backed button variants — must be checked before the generic WBP_AGS_ catch-all below.
	const bool bIsCommonButton =
		ClassPath.EndsWith(TEXT("/WBP_AGS_CommonButton.WBP_AGS_CommonButton_C"))
		|| ClassPath.EndsWith(TEXT("/WBP_AGS_CommonSecondaryButton.WBP_AGS_CommonSecondaryButton_C"))
		|| ClassPath.EndsWith(TEXT("/WBP_AGS_CommonDangerButton.WBP_AGS_CommonDangerButton_C"));
	if (bIsCommonButton)
	{
		return UAGSCommonButtonBase::StaticClass();
	}
	if (ClassPath.EndsWith(TEXT("/WBP_AGS_CommonIconButton.WBP_AGS_CommonIconButton_C")))
	{
		return UAGSCommonIconButtonBase::StaticClass();
	}

	if (WidgetType == TEXT("AGSBadge")
		|| WidgetType == TEXT("AGSCurrencyPill")
		|| WidgetType == TEXT("AGSKeyValueRow")
		|| WidgetType == TEXT("AGSSectionHeader")
		|| WidgetType == TEXT("AGSToast")
		|| WidgetType == TEXT("AGSDivider")
		|| ClassPath.StartsWith(TEXT("/AccelByteUITools/AGSUI/Core/WBP_AGS_")))
	{
		return UAGSLabelValueWidgetBase::StaticClass();
	}
	return nullptr;
}

UClass* ExpectedWidgetClassForNode(const TSharedPtr<FJsonObject>& Node)
{
	if (!Node.IsValid())
	{
		return nullptr;
	}

	FString WidgetType;
	Node->TryGetStringField(TEXT("type"), WidgetType);
	FString ClassPath;
	Node->TryGetStringField(TEXT("class_path"), ClassPath);

	if (UClass* AgsCoreClass = ExpectedAgsCoreWidgetClass(WidgetType, ClassPath))
	{
		return AgsCoreClass;
	}
	if (UClass* NativeClass = ExpectedNativeWidgetClass(WidgetType))
	{
		return NativeClass;
	}
	if (!ClassPath.IsEmpty())
	{
		return LoadClass<UWidget>(nullptr, *ClassPath);
	}
	return nullptr;
}

void CollectWidgetClassExpectations(const TSharedPtr<FJsonObject>& Node, TArray<FWidgetClassExpectation>& OutExpectations)
{
	if (!Node.IsValid())
	{
		return;
	}

	bool bIsVariable = false;
	Node->TryGetBoolField(TEXT("is_variable"), bIsVariable);
	FString WidgetName;
	if (bIsVariable && Node->TryGetStringField(TEXT("name"), WidgetName) && !WidgetName.IsEmpty())
	{
		if (UClass* ExpectedClass = ExpectedWidgetClassForNode(Node))
		{
			OutExpectations.Add({ WidgetName, ExpectedClass->GetPathName() });
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (Node->TryGetArrayField(TEXT("children"), Children))
	{
		for (const TSharedPtr<FJsonValue>& ChildValue : *Children)
		{
			CollectWidgetClassExpectations(ChildValue.IsValid() ? ChildValue->AsObject() : nullptr, OutExpectations);
		}
	}
}

void CollectCollectionEntryExpectations(const TSharedPtr<FJsonObject>& Node, TArray<FCollectionEntryExpectation>& OutExpectations)
{
	if (!Node.IsValid())
	{
		return;
	}

	FString WidgetName;
	FString EntryWidgetClassPath;
	if (Node->TryGetStringField(TEXT("name"), WidgetName)
		&& Node->TryGetStringField(TEXT("entry_widget_class"), EntryWidgetClassPath)
		&& !WidgetName.IsEmpty()
		&& !EntryWidgetClassPath.IsEmpty())
	{
		OutExpectations.Add({ WidgetName, EntryWidgetClassPath });
	}

	const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
	if (Node->TryGetArrayField(TEXT("children"), Children))
	{
		for (const TSharedPtr<FJsonValue>& ChildValue : *Children)
		{
			CollectCollectionEntryExpectations(ChildValue.IsValid() ? ChildValue->AsObject() : nullptr, OutExpectations);
		}
	}
}

UClass* ReadCollectionEntryWidgetClass(const UListViewBase* CollectionWidget)
{
	if (!CollectionWidget)
	{
		return nullptr;
	}

	return CollectionWidget->GetEntryWidgetClass();
}

FString FormatCollectionEntryAssignment(
	const FString& WidgetName,
	const FString& ExpectedEntryWidgetClassPath,
	const FString& ActualEntryWidgetClassPath,
	const bool bVerified)
{
	return FString::Printf(
		TEXT("%s|%s|%s|%s"),
		*WidgetName,
		*ExpectedEntryWidgetClassPath,
		*ActualEntryWidgetClassPath,
		bVerified ? TEXT("true") : TEXT("false"));
}

FString FormatWidgetClassAssignment(
	const FString& WidgetName,
	const FString& ExpectedWidgetClassPath,
	const FString& ActualWidgetClassPath,
	const FString& ClassStability,
	const bool bVerified)
{
	return FString::Printf(
		TEXT("%s|%s|%s|%s|%s"),
		*WidgetName,
		*ExpectedWidgetClassPath,
		*ActualWidgetClassPath,
		*ClassStability,
		bVerified ? TEXT("true") : TEXT("false"));
}

FString FormatParentBindingAssignment(
	const FString& WidgetName,
	const FString& ExpectedWidgetClassPath,
	const FString& ActualPropertyClassPath,
	const FString& BindingMeta,
	const FString& ParentClassPath,
	const bool bVerified)
{
	return FString::Printf(
		TEXT("%s|%s|%s|%s|%s|%s"),
		*WidgetName,
		*ExpectedWidgetClassPath,
		*ActualPropertyClassPath,
		*BindingMeta,
		*ParentClassPath,
		bVerified ? TEXT("true") : TEXT("false"));
}

bool ParseWidgetClassExpectations(const FString& SpecJson, TArray<FWidgetClassExpectation>& OutExpectations, FString& OutError)
{
	OutExpectations.Reset();

	if (SpecJson.IsEmpty())
	{
		OutError.Reset();
		return true;
	}

	TSharedPtr<FJsonObject> SpecObject;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(SpecJson);
	if (!FJsonSerializer::Deserialize(Reader, SpecObject) || !SpecObject.IsValid())
	{
		OutError = TEXT("SpecJson is not a valid JSON object.");
		return false;
	}

	const TSharedPtr<FJsonObject>* RootNode = nullptr;
	if (!SpecObject->TryGetObjectField(TEXT("root"), RootNode))
	{
		OutError = TEXT("SpecJson requires a 'root' object.");
		return false;
	}

	CollectWidgetClassExpectations(*RootNode, OutExpectations);
	OutError.Reset();
	return true;
}

bool IsProjectScriptBackedParentClassPath(const FString& ParentClassPath)
{
	FString ModuleAndClass = ParentClassPath;
	if (!ModuleAndClass.RemoveFromStart(TEXT("/Script/")))
	{
		return false;
	}

	FString ModuleName;
	if (!ModuleAndClass.Split(TEXT("."), &ModuleName, nullptr))
	{
		return false;
	}

	return ModuleName != TEXT("UMG")
		&& ModuleName != TEXT("CommonUI")
		&& ModuleName != TEXT("AccelByteUITools");
}
#endif
}

bool UAccelByteUIToolsLibrary::CreateWidgetBlueprint(const FString& AssetPath, const FString& ParentClassPath, const bool bForce, FString& OutError)
{
#if WITH_EDITOR
	UClass* ParentClass = LoadClass<UUserWidget>(nullptr, *ParentClassPath);
	if (!ParentClass)
	{
		OutError = FString::Printf(TEXT("Parent class could not be loaded: %s"), *ParentClassPath);
		return false;
	}

	if (UEditorAssetLibrary::DoesAssetExist(AssetPath) || (bForce && FPackageName::DoesPackageExist(AssetPath)))
	{
		if (!bForce)
		{
			OutError = FString::Printf(TEXT("Asset already exists: %s"), *AssetPath);
			return false;
		}
		// Same-parent regenerations are safest in place: dependent widgets can keep
		// their references, and PopulateWidgetBlueprintFromJson rebuilds the tree.
		UObject* ExistingAsset = UEditorAssetLibrary::LoadAsset(AssetPath);
		if (UWidgetBlueprint* ExistingWidgetBlueprint = Cast<UWidgetBlueprint>(ExistingAsset))
		{
			if (ExistingWidgetBlueprint->ParentClass == ParentClass)
			{
				if (GEditor)
				{
					if (UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>())
					{
						AssetEditorSubsystem->CloseAllEditorsForAsset(ExistingAsset);
					}
				}

				UE_LOG(LogAccelByteUITools, Display,
					TEXT("Reusing existing Widget Blueprint %s for in-place regeneration."),
					*AssetPath);
				OutError.Reset();
				return true;
			}
		}

		if (ExistingAsset)
		{
			if (GEditor)
			{
				if (UAssetEditorSubsystem* AssetEditorSubsystem = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>())
				{
					AssetEditorSubsystem->CloseAllEditorsForAsset(ExistingAsset);
				}
			}
		}

		bool bDeleted = UEditorAssetLibrary::DeleteAsset(AssetPath);
		if (!bDeleted)
		{
			OutError = FString::Printf(
				TEXT("Existing asset could not be deleted for parent-class recreation: %s. Restart the editor or delete the asset manually, then try again."),
				*AssetPath);
			return false;
		}
		CollectGarbage(GARBAGE_COLLECTION_KEEPFLAGS);
	}

	FString PackagePath;
	FString AssetName;
	if (!AssetPath.Split(TEXT("/"), &PackagePath, &AssetName, ESearchCase::CaseSensitive, ESearchDir::FromEnd))
	{
		OutError = FString::Printf(TEXT("Invalid asset path: %s"), *AssetPath);
		return false;
	}

	UWidgetBlueprintFactory* Factory = NewObject<UWidgetBlueprintFactory>();
	Factory->ParentClass = ParentClass;

	FAssetToolsModule& AssetToolsModule = FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools"));
	UObject* CreatedAsset = AssetToolsModule.Get().CreateAsset(AssetName, PackagePath, UWidgetBlueprint::StaticClass(), Factory);
	if (!CreatedAsset)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint asset could not be created: %s"), *AssetPath);
		return false;
	}

	OutError.Reset();
	return true;
#else
	OutError = TEXT("CreateWidgetBlueprint is editor-only.");
	return false;
#endif
}

bool UAccelByteUIToolsLibrary::PopulateWidgetBlueprintFromJson(const FString& AssetPath, const FString& SpecJson, FString& OutError)
{
#if WITH_EDITOR
	UWidgetBlueprint* WidgetBlueprint = LoadObject<UWidgetBlueprint>(nullptr, *AssetPath);
	if (!WidgetBlueprint)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint asset could not be loaded: %s"), *AssetPath);
		return false;
	}

	TSharedPtr<FJsonObject> SpecObject;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(SpecJson);
	if (!FJsonSerializer::Deserialize(Reader, SpecObject) || !SpecObject.IsValid())
	{
		OutError = TEXT("SpecJson is not a valid JSON object.");
		return false;
	}

	const TSharedPtr<FJsonObject>* RootNode = nullptr;
	if (!SpecObject->TryGetObjectField(TEXT("root"), RootNode))
	{
		OutError = TEXT("SpecJson requires a 'root' object.");
		return false;
	}

	UWidgetTree* WidgetTree = WidgetBlueprint->WidgetTree;
	if (!WidgetTree)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint has no WidgetTree: %s"), *AssetPath);
		return false;
	}

	WidgetBlueprint->Modify();
	WidgetTree->Modify();
	RemoveWidgetTreeSourceWidgets(WidgetBlueprint);

	UWidget* RootWidget = BuildWidgetNode(WidgetTree, *RootNode, OutError);
	if (!RootWidget)
	{
		return false;
	}

	WidgetTree->RootWidget = RootWidget;
	ReconcileWidgetVariables(WidgetBlueprint);

	// Guard: clear bIsVariable on any widget that reconciliation failed to register in the GUID map,
	// so ValidateAndFixUpVariableGuids never fires an ensure during blueprint compilation.
	WidgetBlueprint->ForEachSourceWidget([WidgetBlueprint](UWidget* Widget)
	{
		if (Widget && Widget->bIsVariable
			&& !WidgetBlueprint->WidgetVariableNameToGuidMap.Contains(Widget->GetFName()))
		{
			Widget->Modify();
			Widget->bIsVariable = false;
		}
	});

	FKismetEditorUtilities::CompileBlueprint(WidgetBlueprint);

	FString VariantStr;
	if (SpecObject->TryGetStringField(TEXT("variant"), VariantStr) && WidgetBlueprint->GeneratedClass)
	{
		EAGSButtonVariant ButtonVariant = EAGSButtonVariant::Primary;
		if (VariantStr.Equals(TEXT("Secondary"), ESearchCase::IgnoreCase))   ButtonVariant = EAGSButtonVariant::Secondary;
		else if (VariantStr.Equals(TEXT("Danger"), ESearchCase::IgnoreCase)) ButtonVariant = EAGSButtonVariant::Danger;
		else if (VariantStr.Equals(TEXT("Icon"), ESearchCase::IgnoreCase))   ButtonVariant = EAGSButtonVariant::Icon;

		UObject* CDO = WidgetBlueprint->GeneratedClass->GetDefaultObject();
		if (UAGSButtonBase* Btn = Cast<UAGSButtonBase>(CDO))
		{
			Btn->Variant = ButtonVariant;
			Btn->Modify();
		}
		else if (UAGSCommonButtonBase* CommonBtn = Cast<UAGSCommonButtonBase>(CDO))
		{
			CommonBtn->Variant = ButtonVariant;
			CommonBtn->Modify();
		}
	}

	// Bake selected-state colors into the Blueprint CDO so tab/toggle buttons display correctly.
	if (WidgetBlueprint->GeneratedClass)
	{
		UObject* CDO = WidgetBlueprint->GeneratedClass->GetDefaultObject();
		if (UAGSButtonBase* Btn = Cast<UAGSButtonBase>(CDO))
		{
			FLinearColor Color;
			if (ReadColor(SpecObject, TEXT("selected_color"), Color))
			{
				Btn->SelectedColor = Color;
				Btn->Modify();
			}
			if (ReadColor(SpecObject, TEXT("selected_text_color"), Color))
			{
				Btn->SelectedTextColor = Color;
				Btn->Modify();
			}
		}
	}

	WidgetBlueprint->MarkPackageDirty();
	OutError.Reset();
	return true;
#else
	OutError = TEXT("PopulateWidgetBlueprintFromJson is editor-only.");
	return false;
#endif
}

bool UAccelByteUIToolsLibrary::AddWidgetToWidgetBlueprintFromJson(const FString& AssetPath, const FString& ParentWidgetName, const FString& WidgetJson, FString& OutError)
{
#if WITH_EDITOR
	UE_LOG(LogAccelByteUITools, Display, TEXT("Patch start asset=%s parent=%s widget=%s"), *AssetPath, *ParentWidgetName, *WidgetJson);

	UWidgetBlueprint* WidgetBlueprint = LoadObject<UWidgetBlueprint>(nullptr, *AssetPath);
	if (!WidgetBlueprint)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint asset could not be loaded: %s"), *AssetPath);
		return false;
	}

	UWidgetTree* WidgetTree = WidgetBlueprint->WidgetTree;
	if (!WidgetTree)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint has no WidgetTree: %s"), *AssetPath);
		return false;
	}

	TSharedPtr<FJsonObject> WidgetObject;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(WidgetJson);
	if (!FJsonSerializer::Deserialize(Reader, WidgetObject) || !WidgetObject.IsValid())
	{
		OutError = TEXT("WidgetJson is not a valid JSON object.");
		return false;
	}

	UPanelWidget* ParentWidget = FindPanelWidgetByName(WidgetTree, ParentWidgetName);
	if (!ParentWidget)
	{
		OutError = FString::Printf(TEXT("Parent panel widget could not be found: %s"), *ParentWidgetName);
		return false;
	}

	WidgetBlueprint->Modify();
	WidgetTree->Modify();
	ParentWidget->Modify();

	FString WidgetName;
	if (!WidgetObject->TryGetStringField(TEXT("name"), WidgetName) || WidgetName.IsEmpty())
	{
		OutError = TEXT("Widget JSON is missing required string field: name");
		return false;
	}

	UWidget* ExistingWidget = WidgetTree->FindWidget(FName(*WidgetName));
	if (ExistingWidget)
	{
		if (WidgetBlueprint->WidgetVariableNameToGuidMap.Contains(ExistingWidget->GetFName()))
		{
			WidgetBlueprint->OnVariableRemoved(ExistingWidget->GetFName());
		}
		RemoveGeneratedWidget(WidgetBlueprint, ExistingWidget);
	}

	UWidget* NewWidget = BuildWidgetNode(WidgetTree, WidgetObject, OutError);
	if (!NewWidget)
	{
		UE_LOG(LogAccelByteUITools, Error, TEXT("BuildWidgetNode failed: %s"), *OutError);
		return false;
	}

	if (!AttachWidget(ParentWidget, NewWidget, WidgetObject, OutError))
	{
		UE_LOG(LogAccelByteUITools, Error, TEXT("AttachWidget failed: %s"), *OutError);
		return false;
	}

	ReconcileWidgetVariables(WidgetBlueprint);

	// Guard: clear bIsVariable on any widget that reconciliation failed to register in the GUID map,
	// so ValidateAndFixUpVariableGuids never fires an ensure during blueprint compilation.
	WidgetBlueprint->ForEachSourceWidget([WidgetBlueprint](UWidget* Widget)
	{
		if (Widget && Widget->bIsVariable
			&& !WidgetBlueprint->WidgetVariableNameToGuidMap.Contains(Widget->GetFName()))
		{
			Widget->Modify();
			Widget->bIsVariable = false;
		}
	});

	UE_LOG(LogAccelByteUITools, Display, TEXT("Patch compiling widget=%s parent_children=%d"), *NewWidget->GetName(), ParentWidget->GetChildrenCount());
	FKismetEditorUtilities::CompileBlueprint(WidgetBlueprint);
	WidgetBlueprint->MarkPackageDirty();
	OutError.Reset();
	UE_LOG(LogAccelByteUITools, Display, TEXT("Patch succeeded widget=%s"), *NewWidget->GetName());
	return true;
#else
	OutError = TEXT("AddWidgetToWidgetBlueprintFromJson is editor-only.");
	return false;
#endif
}

bool UAccelByteUIToolsLibrary::UpdateWidgetPropertiesInWidgetBlueprintFromJson(const FString& AssetPath, const FString& WidgetName, const FString& PropertiesJson, FString& OutError)
{
#if WITH_EDITOR
	UE_LOG(LogAccelByteUITools, Display, TEXT("Property patch start asset=%s widget=%s properties=%s"), *AssetPath, *WidgetName, *PropertiesJson);

	UWidgetBlueprint* WidgetBlueprint = LoadObject<UWidgetBlueprint>(nullptr, *AssetPath);
	if (!WidgetBlueprint)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint asset could not be loaded: %s"), *AssetPath);
		return false;
	}

	UWidgetTree* WidgetTree = WidgetBlueprint->WidgetTree;
	if (!WidgetTree)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint has no WidgetTree: %s"), *AssetPath);
		return false;
	}

	TSharedPtr<FJsonObject> PropertiesObject;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PropertiesJson);
	if (!FJsonSerializer::Deserialize(Reader, PropertiesObject) || !PropertiesObject.IsValid())
	{
		OutError = TEXT("PropertiesJson is not a valid JSON object.");
		return false;
	}

	UWidget* Widget = WidgetTree->FindWidget(FName(*WidgetName));
	if (!Widget)
	{
		OutError = FString::Printf(TEXT("Widget could not be found: %s"), *WidgetName);
		return false;
	}

	WidgetBlueprint->Modify();
	WidgetTree->Modify();
	Widget->Modify();

	if (!ApplyWidgetProperties(Widget, PropertiesObject, OutError))
	{
		return false;
	}

	FKismetEditorUtilities::CompileBlueprint(WidgetBlueprint);
	WidgetBlueprint->MarkPackageDirty();
	OutError.Reset();
	UE_LOG(LogAccelByteUITools, Display, TEXT("Property patch succeeded widget=%s"), *WidgetName);
	return true;
#else
	OutError = TEXT("UpdateWidgetPropertiesInWidgetBlueprintFromJson is editor-only.");
	return false;
#endif
}

int32 UAccelByteUIToolsLibrary::ReadWidgetBlueprintHierarchy(const FString& AssetPath, TArray<FString>& OutWidgetNames, FString& OutError)
{
	OutWidgetNames.Reset();

#if WITH_EDITOR
	UWidgetBlueprint* WidgetBlueprint = LoadObject<UWidgetBlueprint>(nullptr, *AssetPath);
	if (!WidgetBlueprint)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint asset could not be loaded: %s"), *AssetPath);
		return 0;
	}

	if (!WidgetBlueprint->WidgetTree || !WidgetBlueprint->WidgetTree->RootWidget)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint hierarchy is empty: %s"), *AssetPath);
		return 0;
	}

	CollectWidgetNames(WidgetBlueprint->WidgetTree->RootWidget, OutWidgetNames);
	OutError.Reset();
	return OutWidgetNames.Num();
#else
	OutError = TEXT("ReadWidgetBlueprintHierarchy is editor-only.");
	return 0;
#endif
}

bool UAccelByteUIToolsLibrary::VerifyWidgetBlueprintCollectionEntries(const FString& AssetPath, const FString& SpecJson, TArray<FString>& OutCollectionEntryAssignments, FString& OutError)
{
	OutCollectionEntryAssignments.Reset();

#if WITH_EDITOR
	if (SpecJson.IsEmpty())
	{
		OutError.Reset();
		return true;
	}

	TSharedPtr<FJsonObject> SpecObject;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(SpecJson);
	if (!FJsonSerializer::Deserialize(Reader, SpecObject) || !SpecObject.IsValid())
	{
		OutError = TEXT("SpecJson is not a valid JSON object.");
		return false;
	}

	const TSharedPtr<FJsonObject>* RootNode = nullptr;
	if (!SpecObject->TryGetObjectField(TEXT("root"), RootNode))
	{
		OutError = TEXT("SpecJson requires a 'root' object.");
		return false;
	}

	TArray<FCollectionEntryExpectation> Expectations;
	CollectCollectionEntryExpectations(*RootNode, Expectations);
	if (Expectations.IsEmpty())
	{
		OutError.Reset();
		return true;
	}

	UWidgetBlueprint* WidgetBlueprint = LoadObject<UWidgetBlueprint>(nullptr, *AssetPath);
	if (!WidgetBlueprint || !WidgetBlueprint->WidgetTree)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint asset could not be loaded for collection verification: %s"), *AssetPath);
		return false;
	}

	for (const FCollectionEntryExpectation& Expectation : Expectations)
	{
		UWidget* Widget = WidgetBlueprint->WidgetTree->FindWidget(FName(*Expectation.WidgetName));
		if (!Widget)
		{
			OutCollectionEntryAssignments.Add(FormatCollectionEntryAssignment(
				Expectation.WidgetName,
				Expectation.EntryWidgetClassPath,
				TEXT(""),
				false));
			OutError = FString::Printf(TEXT("Collection widget declared in spec was not found: %s"), *Expectation.WidgetName);
			return false;
		}

		UListViewBase* CollectionWidget = Cast<UListViewBase>(Widget);
		if (!CollectionWidget)
		{
			OutCollectionEntryAssignments.Add(FormatCollectionEntryAssignment(
				Expectation.WidgetName,
				Expectation.EntryWidgetClassPath,
				Widget->GetClass() ? Widget->GetClass()->GetPathName() : TEXT(""),
				false));
			OutError = FString::Printf(TEXT("Widget '%s' declares entry_widget_class but is not a ListView, TileView, or TreeView."), *Expectation.WidgetName);
			return false;
		}

		UClass* ExpectedEntryWidgetClass = LoadClass<UUserWidget>(nullptr, *Expectation.EntryWidgetClassPath);
		UClass* ActualEntryWidgetClass = ReadCollectionEntryWidgetClass(CollectionWidget);
		const FString ActualEntryWidgetClassPath = ActualEntryWidgetClass ? ActualEntryWidgetClass->GetPathName() : TEXT("");
		const bool bVerified = ExpectedEntryWidgetClass && ActualEntryWidgetClass == ExpectedEntryWidgetClass;
		OutCollectionEntryAssignments.Add(FormatCollectionEntryAssignment(
			Expectation.WidgetName,
			Expectation.EntryWidgetClassPath,
			ActualEntryWidgetClassPath,
			bVerified));

		if (!ExpectedEntryWidgetClass)
		{
			OutError = FString::Printf(
				TEXT("Entry widget class could not be loaded for collection verification '%s': %s"),
				*Expectation.WidgetName,
				*Expectation.EntryWidgetClassPath);
			return false;
		}

		if (!bVerified)
		{
			OutError = FString::Printf(
				TEXT("Collection widget '%s' did not retain EntryWidgetClass. Expected '%s', actual '%s'."),
				*Expectation.WidgetName,
				*Expectation.EntryWidgetClassPath,
				ActualEntryWidgetClassPath.IsEmpty() ? TEXT("<none>") : *ActualEntryWidgetClassPath);
			return false;
		}
	}

	OutError.Reset();
	return true;
#else
	OutError = TEXT("VerifyWidgetBlueprintCollectionEntries is editor-only.");
	return false;
#endif
}

bool UAccelByteUIToolsLibrary::VerifyExpectedWidgetClassesStable(const FString& SpecJson, TArray<FString>& OutWidgetClassAssignments, FString& OutError)
{
	OutWidgetClassAssignments.Reset();

#if WITH_EDITOR
	TArray<FWidgetClassExpectation> Expectations;
	if (!ParseWidgetClassExpectations(SpecJson, Expectations, OutError))
	{
		return false;
	}
	if (Expectations.IsEmpty())
	{
		OutError.Reset();
		return true;
	}

	for (const FWidgetClassExpectation& Expectation : Expectations)
	{
		UClass* ExpectedClass = LoadClass<UWidget>(nullptr, *Expectation.ExpectedClassPath);
		const FString ActualClassPath = ExpectedClass ? ExpectedClass->GetPathName() : TEXT("");
		FString StaleClassPath;
		const bool bStable = ExpectedClass && !FindStaleLiveCodingClassInChain(ExpectedClass, StaleClassPath);
		const FString ClassStability = bStable ? TEXT("stable") : TEXT("stale_live_coding");
		OutWidgetClassAssignments.Add(FormatWidgetClassAssignment(
			Expectation.WidgetName,
			Expectation.ExpectedClassPath,
			ActualClassPath,
			ClassStability,
			bStable));

		if (!ExpectedClass)
		{
			OutError = FString::Printf(
				TEXT("Expected widget class could not be loaded for widget '%s': %s"),
				*Expectation.WidgetName,
				*Expectation.ExpectedClassPath);
			return false;
		}

		if (!bStable)
		{
			OutError = StaleLiveCodingClassMessage(
				Expectation.WidgetName,
				Expectation.ExpectedClassPath,
				ActualClassPath,
				StaleClassPath);
			return false;
		}
	}

	OutError.Reset();
	return true;
#else
	OutError = TEXT("VerifyExpectedWidgetClassesStable is editor-only.");
	return false;
#endif
}

bool UAccelByteUIToolsLibrary::VerifyParentWidgetBindings(const FString& ParentClassPath, const FString& SpecJson, TArray<FString>& OutBindingAssignments, FString& OutError)
{
	OutBindingAssignments.Reset();

#if WITH_EDITOR
	if (!IsProjectScriptBackedParentClassPath(ParentClassPath))
	{
		OutError.Reset();
		return true;
	}

	TArray<FWidgetClassExpectation> Expectations;
	if (!ParseWidgetClassExpectations(SpecJson, Expectations, OutError))
	{
		return false;
	}
	if (Expectations.IsEmpty())
	{
		OutError.Reset();
		return true;
	}

	UClass* ParentClass = LoadClass<UUserWidget>(nullptr, *ParentClassPath);
	if (!ParentClass)
	{
		OutError = FString::Printf(TEXT("Parent class could not be loaded for binding verification: %s"), *ParentClassPath);
		return false;
	}

	for (const FWidgetClassExpectation& Expectation : Expectations)
	{
		UClass* ExpectedClass = LoadClass<UWidget>(nullptr, *Expectation.ExpectedClassPath);
		FProperty* Property = ParentClass->FindPropertyByName(FName(*Expectation.WidgetName));
		FObjectPropertyBase* ObjectProperty = CastField<FObjectPropertyBase>(Property);
		UClass* ActualPropertyClass = ObjectProperty ? ObjectProperty->PropertyClass : nullptr;
		const FString ActualPropertyClassPath = ActualPropertyClass ? ActualPropertyClass->GetPathName() : TEXT("");
		const bool bHasBindWidget = Property && Property->HasMetaData(TEXT("BindWidget"));
		const bool bHasBindWidgetOptional = Property && Property->HasMetaData(TEXT("BindWidgetOptional"));
		const FString BindingMeta = bHasBindWidgetOptional
			? TEXT("BindWidgetOptional")
			: (bHasBindWidget ? TEXT("BindWidget") : TEXT(""));
		const bool bClassMatches = ExpectedClass
			&& ActualPropertyClass
			&& (ActualPropertyClass == ExpectedClass || ActualPropertyClass->IsChildOf(ExpectedClass));
		const bool bVerified = bClassMatches && (bHasBindWidget || bHasBindWidgetOptional);

		OutBindingAssignments.Add(FormatParentBindingAssignment(
			Expectation.WidgetName,
			Expectation.ExpectedClassPath,
			ActualPropertyClassPath,
			BindingMeta,
			ParentClassPath,
			bVerified));

		if (!ExpectedClass)
		{
			OutError = FString::Printf(
				TEXT("Expected widget class could not be loaded for binding '%s' on parent class '%s': expected '%s', actual property class '%s'."),
				*Expectation.WidgetName,
				*ParentClassPath,
				*Expectation.ExpectedClassPath,
				ActualPropertyClassPath.IsEmpty() ? TEXT("<none>") : *ActualPropertyClassPath);
			return false;
		}

		if (!Property)
		{
			OutError = FString::Printf(
				TEXT("Parent class '%s' is missing required BindWidget property for widget '%s'. Expected class '%s', actual property class '<missing>'."),
				*ParentClassPath,
				*Expectation.WidgetName,
				*Expectation.ExpectedClassPath);
			return false;
		}

		if (!ObjectProperty)
		{
			OutError = FString::Printf(
				TEXT("Parent class '%s' property '%s' is not an object widget binding. Expected class '%s', actual property class '<non-object>'."),
				*ParentClassPath,
				*Expectation.WidgetName,
				*Expectation.ExpectedClassPath);
			return false;
		}

		if (!bHasBindWidget && !bHasBindWidgetOptional)
		{
			OutError = FString::Printf(
				TEXT("Parent class '%s' property '%s' has no BindWidget or BindWidgetOptional metadata. Expected class '%s', actual property class '%s'."),
				*ParentClassPath,
				*Expectation.WidgetName,
				*Expectation.ExpectedClassPath,
				ActualPropertyClassPath.IsEmpty() ? TEXT("<none>") : *ActualPropertyClassPath);
			return false;
		}

		if (!bClassMatches)
		{
			OutError = FString::Printf(
				TEXT("Parent class '%s' property '%s' has incorrect BindWidget type. Expected class '%s', actual property class '%s'."),
				*ParentClassPath,
				*Expectation.WidgetName,
				*Expectation.ExpectedClassPath,
				ActualPropertyClassPath.IsEmpty() ? TEXT("<none>") : *ActualPropertyClassPath);
			return false;
		}
	}

	OutError.Reset();
	return true;
#else
	OutError = TEXT("VerifyParentWidgetBindings is editor-only.");
	return false;
#endif
}

bool UAccelByteUIToolsLibrary::VerifyWidgetBlueprintClasses(const FString& AssetPath, const FString& SpecJson, TArray<FString>& OutWidgetClassAssignments, FString& OutError)
{
	OutWidgetClassAssignments.Reset();

#if WITH_EDITOR
	TArray<FWidgetClassExpectation> Expectations;
	if (!ParseWidgetClassExpectations(SpecJson, Expectations, OutError))
	{
		return false;
	}
	if (Expectations.IsEmpty())
	{
		OutError.Reset();
		return true;
	}

	UWidgetBlueprint* WidgetBlueprint = LoadObject<UWidgetBlueprint>(nullptr, *AssetPath);
	if (!WidgetBlueprint || !WidgetBlueprint->WidgetTree)
	{
		OutError = FString::Printf(TEXT("Widget Blueprint asset could not be loaded for widget class verification: %s"), *AssetPath);
		return false;
	}

	for (const FWidgetClassExpectation& Expectation : Expectations)
	{
		UWidget* Widget = WidgetBlueprint->WidgetTree->FindWidget(FName(*Expectation.WidgetName));
		if (!Widget)
		{
			OutWidgetClassAssignments.Add(FormatWidgetClassAssignment(
				Expectation.WidgetName,
				Expectation.ExpectedClassPath,
				TEXT(""),
				TEXT(""),
				false));
			OutError = FString::Printf(TEXT("Widget declared in spec was not found during class verification: %s"), *Expectation.WidgetName);
			return false;
		}

		UClass* ExpectedClass = LoadClass<UWidget>(nullptr, *Expectation.ExpectedClassPath);
		UClass* ActualClass = Widget->GetClass();
		const FString ActualClassPath = ActualClass ? ActualClass->GetPathName() : TEXT("");
		FString ExpectedStaleClassPath;
		FString ActualStaleClassPath;
		const bool bExpectedStable = ExpectedClass && !FindStaleLiveCodingClassInChain(ExpectedClass, ExpectedStaleClassPath);
		const bool bActualStable = ActualClass && !FindStaleLiveCodingClassInChain(ActualClass, ActualStaleClassPath);
		const FString ClassStability = (bExpectedStable && bActualStable) ? TEXT("stable") : TEXT("stale_live_coding");
		const bool bVerified = ExpectedClass && ActualClass && ActualClass->IsChildOf(ExpectedClass) && bExpectedStable && bActualStable;
		OutWidgetClassAssignments.Add(FormatWidgetClassAssignment(
			Expectation.WidgetName,
			Expectation.ExpectedClassPath,
			ActualClassPath,
			ClassStability,
			bVerified));

		if (!ExpectedClass)
		{
			OutError = FString::Printf(
				TEXT("Expected widget class could not be loaded for widget '%s': %s"),
				*Expectation.WidgetName,
				*Expectation.ExpectedClassPath);
			return false;
		}

		if (!bExpectedStable || !bActualStable)
		{
			OutError = StaleLiveCodingClassMessage(
				Expectation.WidgetName,
				Expectation.ExpectedClassPath,
				ActualClassPath,
				!ExpectedStaleClassPath.IsEmpty() ? ExpectedStaleClassPath : ActualStaleClassPath);
			return false;
		}

		if (!bVerified)
		{
			OutError = FString::Printf(
				TEXT("Widget '%s' has incorrect class. Expected child of '%s', actual '%s'."),
				*Expectation.WidgetName,
				*Expectation.ExpectedClassPath,
				ActualClassPath.IsEmpty() ? TEXT("<none>") : *ActualClassPath);
			return false;
		}
	}

	OutError.Reset();
	return true;
#else
	OutError = TEXT("VerifyWidgetBlueprintClasses is editor-only.");
	return false;
#endif
}
