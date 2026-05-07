// Copyright (c) 2026 AccelByte Inc. All Rights Reserved.
// This is licensed software from AccelByte Inc, for limitations
// and restrictions contact your company contract manager.

#include "WidgetBlueprintGeneratorLibrary.h"

#if WITH_EDITOR
#include "AssetToolsModule.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/ContentWidget.h"
#include "Components/EditableTextBox.h"
#include "Components/HorizontalBox.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/PanelWidget.h"
#include "Components/SizeBox.h"
#include "Components/Spacer.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Dom/JsonObject.h"
#include "EditorAssetLibrary.h"
#include "Layout/Anchors.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/TextProperty.h"
#include "Blueprint/UserWidget.h"
#include "WidgetBlueprint.h"
#include "WidgetBlueprintFactory.h"

DEFINE_LOG_CATEGORY_STATIC(LogWidgetBlueprintGenerator, Log, All);
#endif

namespace
{
#if WITH_EDITOR
UClass* ResolveWidgetClass(const TSharedPtr<FJsonObject>& Node)
{
	FString ClassPath;
	if (Node.IsValid() && Node->TryGetStringField(TEXT("class_path"), ClassPath))
	{
		return LoadClass<UWidget>(nullptr, *ClassPath);
	}

	FString WidgetType;
	if (!Node.IsValid() || !Node->TryGetStringField(TEXT("type"), WidgetType))
	{
		return nullptr;
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

void ApplyWidgetProperties(UWidget* Widget, const TSharedPtr<FJsonObject>& Node)
{
	if (!Widget || !Node.IsValid())
	{
		return;
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

		if (FTextProperty* TextProperty = FindFProperty<FTextProperty>(Widget->GetClass(), TEXT("ButtonText")))
		{
			TextProperty->SetPropertyValue_InContainer(Widget, FText::FromString(Text));
		}
	}

	FString HintText;
	if (Node->TryGetStringField(TEXT("hint_text"), HintText))
	{
		if (UEditableTextBox* EditableTextBox = Cast<UEditableTextBox>(Widget))
		{
			EditableTextBox->SetHintText(FText::FromString(HintText));
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
			CanvasSlot->SetPosition(ReadVector2D(*SlotObject, TEXT("position"), FVector2D::ZeroVector));
			CanvasSlot->SetSize(ReadVector2D(*SlotObject, TEXT("size"), FVector2D(100.0f, 40.0f)));
			CanvasSlot->SetAnchors(ReadAnchors(*SlotObject, TEXT("anchors"), CanvasSlot->GetAnchors()));
			CanvasSlot->SetAlignment(ReadVector2D(*SlotObject, TEXT("alignment"), CanvasSlot->GetAlignment()));
		}
		return true;
	}

	if (UPanelWidget* PanelWidget = Cast<UPanelWidget>(Parent))
	{
		if (PanelWidget->AddChild(Child))
		{
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

	ApplyWidgetProperties(Widget, Node);

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

void RegisterWidgetVariables(UWidgetBlueprint* WidgetBlueprint, UWidget* Widget)
{
	if (!WidgetBlueprint || !Widget)
	{
		return;
	}

	if (!WidgetBlueprint->WidgetVariableNameToGuidMap.Contains(Widget->GetFName()))
	{
		WidgetBlueprint->OnVariableAdded(Widget->GetFName());
	}

	if (UPanelWidget* PanelWidget = Cast<UPanelWidget>(Widget))
	{
		for (int32 ChildIndex = 0; ChildIndex < PanelWidget->GetChildrenCount(); ++ChildIndex)
		{
			RegisterWidgetVariables(WidgetBlueprint, PanelWidget->GetChildAt(ChildIndex));
		}
	}
	else if (UContentWidget* ContentWidget = Cast<UContentWidget>(Widget))
	{
		RegisterWidgetVariables(WidgetBlueprint, ContentWidget->GetContent());
	}
}
#endif
}

bool UWidgetBlueprintGeneratorLibrary::CreateWidgetBlueprint(const FString& AssetPath, const FString& ParentClassPath, const bool bForce, FString& OutError)
{
#if WITH_EDITOR
	UClass* ParentClass = LoadClass<UUserWidget>(nullptr, *ParentClassPath);
	if (!ParentClass)
	{
		OutError = FString::Printf(TEXT("Parent class could not be loaded: %s"), *ParentClassPath);
		return false;
	}

	if (UEditorAssetLibrary::DoesAssetExist(AssetPath))
	{
		if (!bForce)
		{
			OutError = FString::Printf(TEXT("Asset already exists: %s"), *AssetPath);
			return false;
		}
		if (!UEditorAssetLibrary::DeleteAsset(AssetPath))
		{
			OutError = FString::Printf(TEXT("Existing asset could not be deleted: %s"), *AssetPath);
			return false;
		}
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

bool UWidgetBlueprintGeneratorLibrary::PopulateWidgetBlueprintFromJson(const FString& AssetPath, const FString& SpecJson, FString& OutError)
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
	UWidget* PreviousRootWidget = WidgetTree->RootWidget;
	WidgetTree->RootWidget = nullptr;

	UWidget* RootWidget = BuildWidgetNode(WidgetTree, *RootNode, OutError);
	if (!RootWidget)
	{
		WidgetTree->RootWidget = PreviousRootWidget;
		return false;
	}

	WidgetTree->RootWidget = RootWidget;
	RegisterWidgetVariables(WidgetBlueprint, RootWidget);
	FKismetEditorUtilities::CompileBlueprint(WidgetBlueprint);
	WidgetBlueprint->MarkPackageDirty();
	OutError.Reset();
	return true;
#else
	OutError = TEXT("PopulateWidgetBlueprintFromJson is editor-only.");
	return false;
#endif
}

bool UWidgetBlueprintGeneratorLibrary::AddWidgetToWidgetBlueprintFromJson(const FString& AssetPath, const FString& ParentWidgetName, const FString& WidgetJson, FString& OutError)
{
#if WITH_EDITOR
	UE_LOG(LogWidgetBlueprintGenerator, Display, TEXT("Patch start asset=%s parent=%s widget=%s"), *AssetPath, *ParentWidgetName, *WidgetJson);

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
		WidgetTree->RemoveWidget(ExistingWidget);
	}

	UWidget* NewWidget = BuildWidgetNode(WidgetTree, WidgetObject, OutError);
	if (!NewWidget)
	{
		UE_LOG(LogWidgetBlueprintGenerator, Error, TEXT("BuildWidgetNode failed: %s"), *OutError);
		return false;
	}

	if (!AttachWidget(ParentWidget, NewWidget, WidgetObject, OutError))
	{
		UE_LOG(LogWidgetBlueprintGenerator, Error, TEXT("AttachWidget failed: %s"), *OutError);
		return false;
	}

	RegisterWidgetVariables(WidgetBlueprint, NewWidget);
	UE_LOG(LogWidgetBlueprintGenerator, Display, TEXT("Patch compiling widget=%s parent_children=%d"), *NewWidget->GetName(), ParentWidget->GetChildrenCount());
	FKismetEditorUtilities::CompileBlueprint(WidgetBlueprint);
	WidgetBlueprint->MarkPackageDirty();
	OutError.Reset();
	UE_LOG(LogWidgetBlueprintGenerator, Display, TEXT("Patch succeeded widget=%s"), *NewWidget->GetName());
	return true;
#else
	OutError = TEXT("AddWidgetToWidgetBlueprintFromJson is editor-only.");
	return false;
#endif
}

int32 UWidgetBlueprintGeneratorLibrary::ReadWidgetBlueprintHierarchy(const FString& AssetPath, TArray<FString>& OutWidgetNames, FString& OutError)
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
