from pathlib import Path
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HEADER = PLUGIN_ROOT / "Source" / "AccelByteUITools" / "Public" / "AGSUI" / "AGSWidgetBase.h"
SOURCE = PLUGIN_ROOT / "Source" / "AccelByteUITools" / "Private" / "AGSUI" / "AGSWidgetBase.cpp"
PLUGIN_README = PLUGIN_ROOT / "README.md"
TOOLS_README = PLUGIN_ROOT / "Tools" / "README.md"
THEME = PLUGIN_ROOT / "Tools" / "specs" / "THEME.md"
EDITOR_LIBRARY = (
    PLUGIN_ROOT
    / "Source"
    / "AccelByteUIToolsEditor"
    / "Private"
    / "AccelByteUIToolsLibrary.cpp"
)
EDITOR_MODULE = (
    PLUGIN_ROOT
    / "Source"
    / "AccelByteUIToolsEditor"
    / "Private"
    / "AccelByteUIToolsEditorModule.cpp"
)


class AGSCppContractTests(unittest.TestCase):
    def test_widget_base_is_minimal_user_widget(self):
        header = HEADER.read_text(encoding="utf-8")

        self.assertIn("class ACCELBYTEUITOOLS_API UAGSWidgetBase : public UUserWidget", header)
        self.assertIn("virtual void SetDisabled(bool bInDisabled);", header)
        for forbidden in (
            "SetState(EAGSUIState InState)",
            "SetLoading(bool bInLoading)",
            "SetStatus(EAGSStatusType InStatusType",
            "SetError(const FText& InMessage)",
            "SetLabel(const FText& InLabel)",
            "SetValue(const FText& InValue)",
            "PrimaryButton",
            "SubmitButton",
            "ValueInput",
            "LabelText",
            "StatusText",
            "ErrorText",
        ):
            self.assertNotIn(forbidden, _class_body(header, "UAGSWidgetBase"))

    def test_focused_native_widget_contract_classes_exist(self):
        header = HEADER.read_text(encoding="utf-8")
        source = SOURCE.read_text(encoding="utf-8")

        expected = {
            "UAGSStateWidgetBase : public UAGSWidgetBase": (
                "SetState(EAGSUIState InState)",
                "IdlePanel",
                "ErrorPanel",
            ),
            "UAGSLabelValueWidgetBase : public UAGSWidgetBase, public IUserObjectListEntry": (
                "SetLabel(const FText& InLabel)",
                "SetValue(const FText& InValue)",
                "NativeOnListItemObjectSet",
                "ListItemObject",
                "UTextBlock",
            ),
            "UAGSButtonBase : public UUserWidget": (
                "SetLabel(const FText& InLabel)",
                "ButtonText",
                "EAGSButtonVariant",
            ),
            "UAGSTextInputBase : public UAGSWidgetBase": (
                "ValueInput",
                "SubmitButton",
                "OnSubmit",
            ),
            "UAGSStatusMessageBase : public UAGSLabelValueWidgetBase": (
                "SetStatus(EAGSStatusType InStatusType",
                "SetError(const FText& InMessage)",
            ),
            "UAGSActionPanelBase : public UAGSStateWidgetBase": (
                "ConfirmButton",
                "CancelButton",
                "RetryButton",
            ),
            "UAGSListRowBase : public UAGSLabelValueWidgetBase": (),
            "UAGSFeatureBlockBase : public UAGSStateWidgetBase, public IUserObjectListEntry": (
                "NativeOnListItemObjectSet",
                "ListItemObject",
            ),
            "UAGSPanelBase : public UAGSStateWidgetBase": (),
        }
        for declaration, members in expected.items():
            self.assertIn(declaration, header)
            body = _class_body(header, declaration.split(" : ", 1)[0])
            for member in members:
                self.assertIn(member, body)

        self.assertIn("void UAGSStateWidgetBase::SetState", source)
        self.assertIn("void UAGSStateWidgetBase::UpdateStateVisibility", source)
        self.assertIn("EAGSUIState CurrentState = EAGSUIState::Success", header)
        self.assertIn("bIsLoading ? EAGSUIState::Loading : EAGSUIState::Success", source)
        self.assertIn("void UAGSLabelValueWidgetBase::NativeOnListItemObjectSet", source)
        self.assertIn("void UAGSFeatureBlockBase::NativeOnListItemObjectSet", source)

    def test_editor_generator_supports_responsive_widget_classes(self):
        source = EDITOR_LIBRARY.read_text(encoding="utf-8")

        for include in (
            '#include "Components/SafeZone.h"',
            '#include "Components/ScaleBox.h"',
            '#include "Components/ListViewBase.h"',
            '#include "Components/ListView.h"',
            '#include "Components/TileView.h"',
            '#include "Components/TreeView.h"',
            '#include "Components/WrapBox.h"',
            '#include "Components/WrapBoxSlot.h"',
            '#include "Blueprint/IUserObjectListEntry.h"',
        ):
            self.assertIn(include, source)

        for widget_type, static_class in (
            ('TEXT("SafeZone")', "USafeZone::StaticClass()"),
            ('TEXT("ScaleBox")', "UScaleBox::StaticClass()"),
            ('TEXT("ListView")', "UListView::StaticClass()"),
            ('TEXT("TileView")', "UTileView::StaticClass()"),
            ('TEXT("TreeView")', "UTreeView::StaticClass()"),
            ('TEXT("WrapBox")', "UWrapBox::StaticClass()"),
        ):
            self.assertIn(widget_type, source)
            self.assertIn(static_class, source)

        self.assertIn("UWrapBoxSlot", source)
        self.assertIn("EntryWidgetClass", source)
        self.assertIn("GetEntryWidgetClass", source)
        self.assertIn("CollectionWidget->Modify()", source)
        self.assertIn("SetEntryWidth", source)
        self.assertIn("SetEntryHeight", source)
        self.assertIn("SetHorizontalEntrySpacing", source)
        self.assertIn("SetVerticalEntrySpacing", source)
        self.assertIn("VerifyWidgetBlueprintCollectionEntries", source)
        self.assertIn("did not retain EntryWidgetClass", source)
        self.assertIn("Reusing existing Widget Blueprint", source)
        self.assertNotIn("ForceDeleteObjects", source)
        self.assertIn("ImplementsInterface(UUserObjectListEntry::StaticClass())", source)
        self.assertIn("must implement UserObjectListEntry", source)
        self.assertIn("Entry widget class could not be loaded", source)
        self.assertIn('TEXT("hint_color")', source)
        self.assertIn('TEXT("corner_radius")', source)
        self.assertIn('TEXT("border_color")', source)
        self.assertIn('TEXT("border_width")', source)
        self.assertIn('TEXT("hover_color")', source)
        self.assertIn('TEXT("pressed_color")', source)
        self.assertIn("ESlateBrushDrawType::RoundedBox", source)
        self.assertIn("MakeRoundedBoxBrush", source)
        self.assertIn("const bool bUseColorAsFill", source)
        self.assertIn("if (bUseColorAsFill)", source)
        self.assertIn("ReadRoundedBoxStyle(StyleObject, FLinearColor::White, false", source)
        self.assertIn("SetBackgroundColor(FSlateColor", source)
        self.assertIn("SetForegroundColor(SlateColor)", source)
        self.assertIn("SetFocusedForegroundColor(SlateColor)", source)
        self.assertIn("WidgetStyle.TextStyle.SetColorAndOpacity", source)
        self.assertIn('!StyleObject->HasTypedField<EJson::Array>(TEXT("color"))', source)
        self.assertIn("SetNormalPadding", source)
        self.assertIn("SetPressedPadding", source)
        self.assertIn("WidgetStyle.SetPadding", source)
        self.assertIn("RemoveWidgetTreeSourceWidgets", source)
        self.assertIn("ForEachSourceWidget", source)
        self.assertIn("MoveWidgetToTransientPackage", source)
        self.assertIn("ReconcileWidgetVariables(WidgetBlueprint)", source)
        self.assertIn("HasParentClassProperty", source)
        self.assertIn("SourceWidgetNames", source)
        self.assertIn("Widget->bIsVariable && HasParentClassProperty", source)
        self.assertIn("OnVariableAdded(SourceWidgetName)", source)
        self.assertIn("Widget->bIsVariable = false", source)
        self.assertIn("WidgetBlueprint->ParentClass", source)
        self.assertNotIn("does not implement UserObjectListEntry; ListView/TileView/TreeView will not function", source)

    def test_generation_reports_verify_collection_entry_assignments(self):
        bridge_source = (
            PLUGIN_ROOT
            / "Source"
            / "AccelByteUIToolsEditor"
            / "Private"
            / "AccelByteUIToolsEditorModule.cpp"
        ).read_text(encoding="utf-8")
        commandlet_source = (
            PLUGIN_ROOT
            / "Source"
            / "AccelByteUIToolsEditor"
            / "Private"
            / "AccelByteUIToolsCommandlet.cpp"
        ).read_text(encoding="utf-8")

        for source in (bridge_source, commandlet_source):
            self.assertIn("verified_collection_entries", source)
            self.assertIn("VerifyWidgetBlueprintCollectionEntries", source)
            self.assertIn("expected_entry_widget_class", source)
            self.assertIn("actual_entry_widget_class", source)

    def test_generation_reports_verify_widget_class_assignments(self):
        editor_library = EDITOR_LIBRARY.read_text(encoding="utf-8")
        library_header = (
            PLUGIN_ROOT
            / "Source"
            / "AccelByteUIToolsEditor"
            / "Public"
            / "AccelByteUIToolsLibrary.h"
        ).read_text(encoding="utf-8")
        bridge_source = (
            PLUGIN_ROOT
            / "Source"
            / "AccelByteUIToolsEditor"
            / "Private"
            / "AccelByteUIToolsEditorModule.cpp"
        ).read_text(encoding="utf-8")
        commandlet_source = (
            PLUGIN_ROOT
            / "Source"
            / "AccelByteUIToolsEditor"
            / "Private"
            / "AccelByteUIToolsCommandlet.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("VerifyWidgetBlueprintClasses", library_header)
        self.assertIn("VerifyExpectedWidgetClassesStable", library_header)
        self.assertIn("VerifyParentWidgetBindings", library_header)
        self.assertIn("VerifyWidgetBlueprintClasses", editor_library)
        self.assertIn("VerifyExpectedWidgetClassesStable", editor_library)
        self.assertIn("VerifyParentWidgetBindings", editor_library)
        self.assertIn("CollectWidgetClassExpectations", editor_library)
        self.assertIn("ExpectedAgsCoreWidgetClass", editor_library)
        self.assertIn("FindPropertyByName", editor_library)
        self.assertIn("BindWidgetOptional", editor_library)
        self.assertIn("backing_binding_mismatch", bridge_source)
        self.assertIn("backing_binding_mismatch", commandlet_source)
        self.assertIn("ContainsStaleLiveCodingClassMarker", editor_library)
        self.assertIn("FindStaleLiveCodingClassInChain", editor_library)
        self.assertIn("stale_live_coding", editor_library)
        self.assertIn("LIVE CODING", editor_library)
        self.assertIn("HOTRELOAD", editor_library)
        self.assertIn("REINST_", editor_library)
        self.assertIn("stale Live Coding class state", editor_library)
        self.assertIn("Restart the editor or run a full rebuild, then regenerate", editor_library)
        self.assertIn("UAGSEmptyStateBase::StaticClass()", editor_library)
        self.assertIn("UAGSTextInputBase::StaticClass()", editor_library)
        self.assertIn('WidgetType == TEXT("AGSTextInput")', editor_library)
        self.assertIn('WidgetType == TEXT("AGSPasswordInput")', editor_library)
        self.assertIn('WidgetType == TEXT("AGSSearchInput")', editor_library)
        self.assertIn("UAGSLoadingIndicatorBase::StaticClass()", editor_library)
        self.assertIn("UAGSErrorStateBase::StaticClass()", editor_library)
        self.assertIn("verify_only", bridge_source)
        self.assertIn("bVerifyOnly", bridge_source)
        self.assertIn("/accelbyte-ui-tools/resolve", bridge_source)
        self.assertIn("HandleResolveRequest", bridge_source)
        self.assertIn("CompleteResolveRequest", bridge_source)
        self.assertIn("resolve_only", bridge_source)
        self.assertIn("expected_collection_entries", bridge_source)
        self.assertIn("Expected child of", editor_library)
        self.assertIn("actual", editor_library)
        for source in (bridge_source, commandlet_source):
            self.assertIn("verified_widget_classes", source)
            self.assertIn("verified_backing_bindings", source)
            self.assertIn("expected_widget_class", source)
            self.assertIn("actual_widget_class", source)
            self.assertIn("expected_property_class", source)
            self.assertIn("actual_property_class", source)
            self.assertIn("class_stability", source)
            self.assertIn("stale_live_coding_class", source)
            self.assertIn("VerifyWidgetBlueprintClasses", source)
            self.assertIn("VerifyParentWidgetBindings", source)

    def test_resolve_bridge_path_does_not_create_or_save_assets(self):
        bridge_source = EDITOR_MODULE.read_text(encoding="utf-8")
        resolve_start = bridge_source.index("bool CompleteResolveRequest(")
        resolve_end = bridge_source.index("bool HandleGenerateRequest(", resolve_start)
        resolve_body = bridge_source[resolve_start:resolve_end]

        self.assertIn("VerifyExpectedWidgetClassesStable", resolve_body)
        self.assertIn("AddExpectedCollectionEntries", resolve_body)
        self.assertNotIn("CreateWidgetBlueprint", resolve_body)
        self.assertNotIn("PopulateWidgetBlueprintFromJson", resolve_body)
        self.assertNotIn("SaveAsset", resolve_body)

    def test_documentation_tracks_native_umg_contract(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in (PLUGIN_README, TOOLS_README, THEME)
        )

        self.assertIn("CommonUI", combined)
        self.assertIn("CommonButtonBase", combined)
        self.assertIn("SafeZone", combined)
        self.assertIn("ScaleBox", combined)
        self.assertIn("WrapBox", combined)
        self.assertIn("StateSwitcher", combined)
        self.assertIn("Overlay", combined)
        self.assertIn("hint_color", combined)
        self.assertIn("corner_radius", combined)
        self.assertIn("border_color", combined)


    def test_common_activatable_base_overrides_focus_target(self):
        header = HEADER.read_text(encoding="utf-8")
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn(
            "UAGSCommonActivatableBase : public UCommonActivatableWidget", header
        )
        self.assertIn("NativeGetDesiredFocusTarget", header)
        self.assertIn("NativeGetDesiredFocusTarget", source)


def _class_body(header: str, class_name: str) -> str:
    marker = f"class ACCELBYTEUITOOLS_API {class_name}"
    start = header.index(marker)
    next_class = header.find("\nUCLASS", start + len(marker))
    return header[start:] if next_class == -1 else header[start:next_class]



if __name__ == "__main__":
    unittest.main()
